import sys, requests, re
import lxml.html 

def fetch_html(url):
	try:
		response = requests.get(url)
		return lxml.html.fromstring(response.content)
	except requests.exceptions.RequestException as e:
		raise SystemExit(e)

wiki_base_url = 'https://en.wikipedia.org'

## Generator that loads the wiki page of the next film in the list
class film_pages(object):
		@staticmethod
		def check_year(row):
			relevant_years = [str(y) for y in range(2010, 2021)]
			for year in relevant_years:
				if len(row.xpath("./td[2]//*[contains(text(), '{}')]".format(year))) > 0:
					return True
			return False

		def __init__(self):
				self.film_list = fetch_html('https://en.wikipedia.org/wiki/List_of_Academy_Award-winning_films')
				self.index = 0
				self.rows = self.film_list.xpath("//span[@id='List_of_films']/following::table[1]/tbody/tr")[1:]
				self.rows = list(filter(lambda row: self.check_year(row), self.rows))
				self.num_films = len(self.rows)

		def __iter__(self):
			return self

		def __next__(self):
			return self.next()

		def next(self):
			if self.index <= self.num_films:
						curr_row = self.rows[self.index]
						curr_film_href = wiki_base_url + curr_row.xpath('.//td[1]//a')[0].attrib['href']
						self.index += 1
						return fetch_html(curr_film_href)
			raise StopIteration()
		
if __name__ == "__main__":
		g = film_pages()
				