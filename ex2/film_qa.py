import sys, requests, re
from lxml import html 
import json
import rdflib

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
	'star', 'cast', #q6-7
}

person_required_fields = {
	'born', # q7
	'occupation', # q8
}


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
						self.index += 1
						return curr_film_href
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
	name = name.replace(" ", "_") # switching spaces for _
	return name

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


def build_ontology_graph(pages_list):
	ontology_graph = rdflib.Graph()
	relations_map = get_relations_map()
	previously_visited = set()

	i = 0
	while True:
		try:
			# res.extend(infobox_crawler(g.next()))
			curr_url = pages_list.next()
			# print("current is:{}".format(curr_url))
			infoboxes_extraced_data = infobox_crawler(curr_url)
			# print("current is:{}".format(infoboxes_extraced_data))
			# print('finished {}...'.format(i))
			print(type(infoboxes_extraced_data))
			for entity in infoboxes_extraced_data:

				entity_name = get_valid_name_for_url(entity['name'])
				entity_infobox = entity['infobox']
				current_entity_object = rdflib.URIRef(BASE_URL+entity_name)
				if entity['entity'] == 'film':
					# check based on a book

					print("flipitotio")
				else:
					# question 9
					if "occupation" in entity_infobox:
						for curr_occupation in entity_infobox['occupation']:
							curr_occupation_ontology = rdflib.URIRef(BASE_URL+get_valid_name_for_url((curr_occupation)))
							curr_relation_ontology = relations_map['occupation']
							ontology_graph.add((current_entity_object, curr_relation_ontology, curr_occupation_ontology))
					# it is a person
					print("pakatoo")

				previously_visited.add(entity['name'])
				i += 1
			print(ontology_graph.serialize(format="turtle").decode("utf-8"))
			break
		except StopIteration:
			break




if __name__ == "__main__":
		g = film_pages()
		res = []
		i = 1
		# infobox_crawler('https://en.wikipedia.org/wiki/Feast_(2014_film)')
		build_ontology_graph(g)

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
		