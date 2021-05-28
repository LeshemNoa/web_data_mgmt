import sys, requests, re
from lxml import html 
import json
import rdflib
import urllib
import sys

wiki_base_url = 'https://en.wikipedia.org'
film_list_url = 'https://en.wikipedia.org/wiki/List_of_Academy_Award-winning_films'
## These are identifier strings that are associated with data points about which we
## are going to answer questions later. That'll allow us to distinguish between
## "interesting data points" that we should follow links in and explore further,
## and "secondary data points" that don't require further page visits.
film_required_fields = {
	'direct', # q1
	'produce', # q2
	# q3 - 'based on'. since answer is boolean we don't need to visit further links
	'release', # q4
	'running time', # q5
	'star', #q6-7
}

person_required_fields = {
	'born', # q7
	'occupation', # q8
}
ONTOLOGY_FILE_NAME = "ontology"

def fetch_html(url):
	try:
		response = requests.get(url)
		return html.fromstring(response.content)
	except requests.exceptions.RequestException as e:
		raise SystemExit(e)

## Iterator for the film list. Gets the wiki page url of the next film in the list
class film_pages(object):
		@staticmethod
		def check_year(row):
			relevant_years = [str(y) for y in range(2010, 2021)]
			for year in relevant_years:
				if len(row.xpath("./td[2]//*[contains(text(), '{}')]".format(year))) > 0:
					return True
			return False

		def __init__(self):
				self.film_list = fetch_html(film_list_url)
				self.index = 0
				self.rows = self.film_list.xpath("//span[@id='List_of_films']/following::table[1]/tbody/tr")[1:]
				self.rows = list(filter(lambda row: self.check_year(row), self.rows))
				self.num_films = len(self.rows)

		def __iter__(self):
			return self

		def __next__(self):
			return self.next()

		def next(self):
			if self.index < self.num_films:
						curr_row = self.rows[self.index]
						curr_film_href = wiki_base_url + curr_row.xpath('.//td[1]//a')[0].attrib['href']
						award_num = curr_row.xpath('.//td[3]')[0].text_content().__str__().strip()
						if award_num.startswith('0'): ## fix for one edge case where there has been a special award
							award_num = '1'
						self.index += 1
						return curr_film_href, award_num
			raise StopIteration()

def should_follow_links(label, is_film_page):
	if not is_film_page:
		return False
	res = False
	for field_id in film_required_fields:
		if field_id in label.lower():
			res = True
	return res

def is_person_field_required(label):
	res = False
	for field_id in person_required_fields:
		if field_id in label.lower():
			res = True
	return res

def get_row_content(row, is_film_page=False):
	data_label = row.xpath('./th[contains(@class, "infobox-label")]')[0]
	for br in data_label.xpath(".//br"):
		br.tail = " " + br.tail if br.tail else " "
	label = data_label.text_content().strip()
	if not is_film_page and not is_person_field_required(label):
		return None, None, None
	follow_links = should_follow_links(label, is_film_page)

	data_cell = row.xpath('./td[contains(@class, "infobox-data")]')
	assert len(data_cell) == 1
	data_cell = data_cell[0]
	data_cell_text = []
	found_links = []

	if not is_film_page and 'born' in label.lower():
		bday = data_cell.xpath('.//*[contains(@class, "bday")]')
		if len(bday) == 1:
			return label, [bday[0].text_content()], found_links
		text = data_cell.text_content().__str__()
		m = re.search(r'[\d]{4}(\/[\d]{4})?', text)
		if m == None: ## conclude: no relevant info in this cell as there's no date.
			return None, None, None	
		else:
			return label, [m[0]], found_links

	data_lists = data_cell.xpath(
		'.//ul[not(contains(@style, "display: inline"))][not(descendant::ul)]'
	)
	assert len(data_lists) <= 1
	## regular text data - not a list
	if len(data_lists) == 0:
		cell_links = data_cell.xpath('./a[not(descendant::sup)]')				
		if len(cell_links) >= 1 and follow_links:
			for link in cell_links:
				found_url = wiki_base_url + link.attrib['href']
				found_links.append(found_url)
		for br in data_cell.xpath(".//br"):
			br.tail = "<br>" + br.tail if br.tail else "<br>"
		for b in data_cell.xpath(".//b"): ## ignore bold text
			b.tail = "<b>" + b.tail if b.tail else "<b>"
		content = data_cell.text_content()
		data_cell_text = list(filter(lambda s: not '<b>' in s, content.split("<br>")))
	## data is a list
	elif len(data_lists) == 1:
		list_items = data_lists[0].xpath('./li')
		for li in list_items:
			## we only care about the link if it's the first child
			li_links = li.xpath('./*[1]/self::a[not(descendant::sup)]')				
			if len(li_links) > 0 and follow_links:
				li_url = wiki_base_url + li.xpath('./a')[0].attrib['href']
				found_links.append(li_url)
			data_cell_text.append(li.text_content())

			## data contains an inline list. We don't add it to the data cell data
			## as it's secondary, but we do go over to scrape that page
			inline_lists = data_cell.xpath('.//ul[contains(@style, "display: inline")]')
			if len(inline_lists) >= 1:
				list_items = inline_lists[0].xpath('./li')
				for li in list_items:
					li_links = li.xpath('./*[1]/self::a[not(descendant::sup)]')
					if len(li_links) > 0 and follow_links:
						li_url = wiki_base_url + li_links[0].attrib['href']
						found_links.append(li_url)

	return label, data_cell_text, found_links

def get_infobox_content(page_url, is_film_page=False):
	wiki_page = fetch_html(page_url)
	infobox_rows = wiki_page.xpath(
		'//table[contains(@class, "infobox")][1]//th[contains(@class, "infobox-label")]/parent::tr'
	)
	pages_to_visit = []
	infobox_content = {}
	if len(infobox_rows) > 0:
		for row in infobox_rows:
			label, data_cell_text, found_links = get_row_content(row, is_film_page)
			if label == None:
				continue
			pages_to_visit.extend(found_links)			
			infobox_content[label.lower()] = data_cell_text
	return infobox_content, pages_to_visit	

def infobox_crawler(base_page_url):
	page_stack = [base_page_url]
	previously_visited = set()
	collected_data = []
	while len(page_stack) > 0:
		page_url = page_stack.pop()
		if page_url not in previously_visited:
			is_film_page = True if page_url == base_page_url else False
			infobox_content, pages_to_visit = get_infobox_content(page_url, is_film_page)
			## TODO: Implement a text sanitation function that cleans weird unicode chars,
			## cite notes, over expanded dates etc, and call it here
			
			## at last, add infobox content to collected data
			if bool(infobox_content):
				collected_data.append({
					'entity': 'film' if is_film_page else 'person',
					'name': page_url.split('/')[-1].replace('_', ' '),
					'url': page_url,
					'infobox': infobox_content,
				})
			page_stack.extend(pages_to_visit)
			previously_visited.add(page_url)

	return collected_data

BASE_URL = "http://example.org/"

def get_valid_name_for_url(name):
	# name = re.sub(r'\([^()]*\)', '', name) # removing parenthesis
	name = name.lstrip()
	name = name.replace(" ", "_")
	name = urllib.parse.unquote(name) # switching spaces for _
	name = name.rstrip("\n")
	return del_reference(name)

def del_reference(text):
	new_text = re.sub('\[\d+\]', '', text)
	return new_text


def get_relations_map():
	return {'direct' : rdflib.URIRef(BASE_URL+'direct'), # q1
			'produce' : rdflib.URIRef(BASE_URL+'produce'), # q2
			'based on' : rdflib.URIRef(BASE_URL+'based_on'), # q2
			'release' : rdflib.URIRef(BASE_URL+'release'), # q4
			'running time' : rdflib.URIRef(BASE_URL+'running_time'), # q5
			'star' : rdflib.URIRef(BASE_URL+'star'),
			'cast': rdflib.URIRef(BASE_URL+'cast'),
			'born': rdflib.URIRef(BASE_URL+'born'), # q7
			'occupation': rdflib.URIRef(BASE_URL+'occupation')}


def is_based_on_a_book(entity):
	if 'based on' in entity:
		return True
	return False

def format_film_name(arguments_list):
	formatted_film_name = ""
	for arg in arguments_list:
		if formatted_film_name == "":
			formatted_film_name = arg
		else:
			formatted_film_name = formatted_film_name+"_"+arg
	print("formattedis:",formatted_film_name)
	return formatted_film_name

def format_query_response(query_response):
	return (query_response.replace(BASE_URL,"")).replace("_"," ")

def format_qery_response_list(query_response_list):
	new_list = []
	for item in query_response_list:
		new_list.append(item[0])
	print("new list", new_list)
	sorted_list = sorted(new_list, key=str.casefold)

	return [format_query_response(item) for item in sorted_list]


def build_ontology_graph(pages_list):
	ontology_graph = rdflib.Graph()
	relations_map = get_relations_map()

	# i = 0
	while True:
		try:
			curr_url, award_num = pages_list.next()
			infoboxes_extraced_data = infobox_crawler(curr_url)
			for entity in infoboxes_extraced_data:
				entity_name = get_valid_name_for_url(entity['name'])
				entity_infobox = entity['infobox']
				current_entity_object = rdflib.URIRef(BASE_URL+entity_name)
				print("entity name is:",entity_name)
				if entity['entity'] == 'film':
					# check based on a book
					# question 1 directed film
					if 'directed by' in entity_infobox:
						for produce in entity_infobox['directed by']:
							curr_starring_ontology = rdflib.URIRef(BASE_URL+get_valid_name_for_url(produce))
							curr_relation_ontology = relations_map['direct']
							ontology_graph.add((current_entity_object, curr_relation_ontology, curr_starring_ontology))

					# question 2 produce film
					if 'produced by' in entity_infobox:
						for produce in entity_infobox['produced by']:
							curr_starring_ontology = rdflib.URIRef(BASE_URL+get_valid_name_for_url(produce))
							curr_relation_ontology = relations_map['produce']
							ontology_graph.add((current_entity_object, curr_relation_ontology, curr_starring_ontology))
					else:
						print(f"{entity_name} is missing produced by")

					# question 3 based on a book
					if 'based on' in entity_infobox:
						based_on_book = True
					else:
						based_on_book = False

					curr_based_on_ontology = rdflib.URIRef(BASE_URL+str(based_on_book))
					curr_relation_ontology = relations_map['based on']
					ontology_graph.add((current_entity_object, curr_relation_ontology, curr_based_on_ontology))

					# question 4 release date TODO after cleaning the date format fix this
					# if 'released date' in entity_infobox:
					# release_date =entity_infobox['release date']
					# curr_release_date_ontology = rdflib.URIRef(BASE_URL+str(release_date))
					# curr_relation_ontology = relations_map['release']
					# ontology_graph.add((current_entity_object, curr_relation_ontology, curr_release_date_ontology))


					# question 5 running time
					if 'running time' in entity_infobox:
						for running_time in entity_infobox['running time']:
							if running_time.find('minutes') > -1:
								curr_running_time_ontology = rdflib.URIRef(BASE_URL+get_valid_name_for_url(running_time))
								curr_relation_ontology = relations_map['running time']
								ontology_graph.add((current_entity_object, curr_relation_ontology, curr_running_time_ontology))
					else:
						print(f"{entity_name} is missing running time")

					# question 7 + 6 person stared in film
					# TODO maybe we need biderctional?
					if 'starring' in entity_infobox:
						for starring in entity_infobox['starring']:
							curr_starring_ontology = rdflib.URIRef(BASE_URL+get_valid_name_for_url((starring)))
							curr_relation_ontology = relations_map['star']
							ontology_graph.add((current_entity_object, curr_relation_ontology, curr_starring_ontology))
					else:
						print(f"{entity_name} is missing starring")



					print("flipitotio")
				else:
					# it is a person
					# question 8 when person was born TODO after cleaning the date format fix this
					# if "born" in entity_infobox:
					# 	print(entity_infobox['born'])
					# 	curr_born_ontology = rdflib.URIRef(BASE_URL+(entity_infobox['born']))
					# 	curr_relation_ontology = relations_map['born']
					# 	ontology_graph.add((current_entity_object, curr_relation_ontology, curr_born_ontology))


					# question 9 what occupies person
					if "occupation" in entity_infobox:
						# forum said lower case
						if ',' in entity_infobox['occupation']:
							entity_infobox['occupation'] = entity_infobox['occupation'].split(',')
						for curr_occupation in entity_infobox['occupation']:
							if ',' in curr_occupation:
								curr_occupation_splitted = curr_occupation.replace(" ","")
								curr_occupation_splitted = curr_occupation_splitted.split(',')
								for current_occupation_splitted in curr_occupation_splitted:
									if current_occupation_splitted != "":
										curr_occupation_ontology = rdflib.URIRef(BASE_URL+get_valid_name_for_url(current_occupation_splitted.lower()))
										curr_relation_ontology = relations_map['occupation']
										ontology_graph.add((current_entity_object, curr_relation_ontology, curr_occupation_ontology))
							else:
								curr_occupation_ontology = rdflib.URIRef(BASE_URL+get_valid_name_for_url(curr_occupation.lower()))
								curr_relation_ontology = relations_map['occupation']
								ontology_graph.add((current_entity_object, curr_relation_ontology, curr_occupation_ontology))
					else:
						print(f"{entity_name} is missing occupation")

					# it is a person
					print("pakatoo")
				# i += 1
				# if i == 12:
				# 	break			# print(ontology_graph.serialize(format="turtle").decode("utf-8"))
		except StopIteration:
				break

	# save ontology_graph to a file
	ontology_graph.serialize(ONTOLOGY_FILE_NAME+".nt", format="nt")
	print("finisihed saving")
	return ontology_graph


def query_graph(ontology_graph, question):
	# TODO add lexicographic sorting
	question = question.replace("?","")
	question_splitted_to_elements = question.split(" ")

	if question_splitted_to_elements[0] == "Who":
		if question_splitted_to_elements[1] == 'directed':
			# question 1 who directed film
			print("q1")
			query_param = format_film_name(question_splitted_to_elements[2:])
			query = "select ?x where { <http://example.org/"+query_param+"> <http://example.org/direct> ?x .}"
			res = ontology_graph.query(query)
		elif question_splitted_to_elements[1] == 'produced':
			# question 2 who produced film
			query_param = format_film_name(question_splitted_to_elements[2:])
			query = "select ?x where { <http://example.org/"+query_param+"> <http://example.org/produce> ?x .}"
			res = ontology_graph.query(query)
		elif question_splitted_to_elements[1] == 'starred':
			# question 6 who starred in film
			query_param = format_film_name(question_splitted_to_elements[3:])
			query = "select ?x where { <http://example.org/"+query_param+"> <http://example.org/star> ?x .}"
			res = ontology_graph.query(query)

		print(str(list(res)))
		# for query_result in list(res)
		print(', '.join(format_qery_response_list(list(res))))
	elif question_splitted_to_elements[0] == "Is":
		# question 3 film based on a book
		list_of_film_args = []
		for elem in question_splitted_to_elements[1:]:
			if elem == "based":
				break
			list_of_film_args.append(elem)
		film = format_film_name(list_of_film_args)
		query = "select ?x where { <http://example.org/"+film+"> <http://example.org/based_on> ?x .}"
		res = ontology_graph.query(query)
		print(list(res))
		if str(list(res)[0][0]) == BASE_URL+"True":
			print("Yes")
		elif str(list(res)[0][0]) == BASE_URL+"False":
			print("No")
		else:
			print("something went wrong")
	# elif question_splitted_to_elements[0]=="When":

	elif question_splitted_to_elements[0] == "How":
		# question 5
		if question_splitted_to_elements[1] == "long":
			query_param = format_film_name(question_splitted_to_elements[3:])
			query = "select ?x where { <http://example.org/"+query_param+"> <http://example.org/running_time> ?x .}"
			res = ontology_graph.query(query)
			print(format_query_response(list(res)[0][0]))

		# question 3 general TODO
		# elif "also" in question_splitted_to_elements:

		# question 2 general
		elif "won" in question_splitted_to_elements:
			query_param = format_film_name(question_splitted_to_elements[3:question_splitted_to_elements.index("won")])
			query = "select (count(?x) as ?count) where { ?x <http://example.org/star> <http://example.org/"+query_param+"> .}"
			res = ontology_graph.query(query)
			print(format_query_response(list(res)[0][0]))

		# question 1 general
		elif question_splitted_to_elements[len(question_splitted_to_elements)-1] == "books":
			query = "select (count(?x) as ?count) where { ?x <http://example.org/based_on> <http://example.org/True> .}"
			res = ontology_graph.query(query)
			print(format_query_response(list(res)[0][0]))
	elif question_splitted_to_elements[0] == "Did":
		person_query_param = format_film_name(question_splitted_to_elements[1:question_splitted_to_elements.index("star")])
		film_query_param = format_film_name(question_splitted_to_elements[question_splitted_to_elements.index("in")+1:])
		print("person", person_query_param)
		print("movie", film_query_param)
		query = "ask where { <http://example.org/"+film_query_param+"> <http://example.org/star> <http://example.org/"+person_query_param+"> .}"
		res = ontology_graph.query(query)
		if len(res) > 0:
			print("Yes")
		else:
			print("No")
		
	else:
		print("unsupported question")

	return ""


if __name__ == "__main__":
		res = []
		i = 1
		argv = sys.argv[1:]
		if argv[0] == 'create':
			g = film_pages()
			build_ontology_graph(g)
		elif argv[0] == 'question':
			# load ontology
			ontology_graph = rdflib.Graph()
			ontology_graph.parse(ONTOLOGY_FILE_NAME+".nt", format="nt")

			# categorize question
			print(f"question is:{argv[1]}")
			query_graph(ontology_graph,argv[1])
		else:
			print("unspported command was given! commands supported are either 'question' or 'create'.")

		# while True:
		# 	try:
		# 		# res.extend(infobox_crawler(g.next()))
		# 		curr_url = g.next()
		# 		print("current is:{}".format(curr_url))
		# 		print("current is:{}".format(infobox_crawler(curr_url)))
		# 		print('finished {}...'.format(i))
		# 		i += 1
		# 		break
		# 	except StopIteration:
		# 		break
		# with open('./ex2/all_film_data.json', 'w') as filehandle:
		# 	json.dump(res, filehandle, indent=4, sort_keys=True)
		