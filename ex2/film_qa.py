import sys, requests, re
from lxml import html 
import json

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
	'birth',
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
	data_lists = data_cell.xpath('.//div[@class="plainlist"]/ul')
	assert len(data_lists) <= 1
	## regular text data - not a list
	if len(data_lists) == 0:
		if len(data_cell.xpath('./a')) == 1 and follow_links:
			data_cell_url = wiki_base_url + data_cell.xpath('./a')[0].attrib['href']
			found_links.append(data_cell_url)
		for br in data_cell.xpath(".//br"):
			br.tail = "<br>" + br.tail if br.tail else "<br>"
		content = data_cell.text_content()
		data_cell_text = content.split("<br>")
	## data is a list
	elif len(data_lists) == 1:
		list_items = data_lists[0].xpath('./li')
		for li in list_items:
			## we only care about the link if it's the first child
			li_links = li.xpath('./*[1]/self::a')				
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
					li_links = li.xpath('*[1]/self::a')
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
			infobox_content[label] = data_cell_text
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

if __name__ == "__main__":
		g = film_pages()
		res = []
		i = 1
		while True:
			try:
				res.extend(infobox_crawler(g.next()))
				print('finished {}...'.format(i))
				i += 1
			except StopIteration:
				break
		with open('./output.json', 'w') as filehandle:
			json.dump(res, filehandle, indent=4, sort_keys=True)
		