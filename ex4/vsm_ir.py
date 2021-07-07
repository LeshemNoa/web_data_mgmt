from lxml import etree
import os, string, re, json
import numpy as np
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import sys
import nltk

def tokenize(s):
	stemmer = PorterStemmer()
	stopword_set = set(stopwords.words('english'))
	## remove punctuations
	s = s.translate(str.maketrans('', '', string.punctuation))
	words = list(filter(lambda w: str.isalpha(w) and not w.lower() in stopword_set, re.split('\s+', s)))
	tokens = [stemmer.stem(w) for w in words]
	word_counts = {}
	for tok in tokens:
		if tok in word_counts:
			word_counts[tok] += 1
		else:
			word_counts[tok] = 1
	return tokens, word_counts

# TODO change names
def tokenize_v2(data):
	tokens_count = {}
	excluded = set(nltk.corpus.stopwords.words('english')).union(set(string.punctuation))
	# excluded = excluded.union({"1","2","3","4","5","6","7","8","9","0"})
	# data = re.sub(r'\d+\.?\d*', '', data)

	unfiltered_question_tokens = nltk.tokenize.word_tokenize(data.lower())
	tokens = [token for token in unfiltered_question_tokens if token not in excluded]
	stemmer = nltk.stem.PorterStemmer()
	question_tokens = [stemmer.stem(token) for token in tokens]
	for tok in question_tokens:
		if tok not in tokens_count:
			tokens_count[tok] = 0
		tokens_count[tok] += 1
	return question_tokens, tokens_count



def build_index(path):
	assert os.path.isdir(path)
	files = os.listdir(path)
	xml_files = list(filter(lambda filename: filename.endswith('.xml'), files))
	index = {}
	doc_num = 0
	all_record_nums = []
	for f in xml_files:
		doc = etree.parse(path + '/' + f)
		records = doc.xpath('//RECORD')
		for r in records:
			doc_num += 1
			record_num = r.xpath('./RECORDNUM/text()')[0].__str__().strip()
			all_record_nums.append(record_num)
			title = r.xpath('./TITLE/text()')
			extract = r.xpath('./EXTRACT/text()')
			abstract = r.xpath('./ABSTRACT/text()')
			all_text = ' '.join(title + extract + abstract)
			words, word_counts = tokenize_v2(all_text)
			max_count = max(list(word_counts.values()))
			for tok in list(word_counts.keys()):
				word_record = {
							'record_num': record_num,
							'occ_count': word_counts[tok],
							'tf': word_counts[tok] / max_count,
						}
				if not tok in index:
					index[tok] = { "occ_list": [word_record] }
				else:
					got = index[tok]
					index[tok]["occ_list"].append(word_record)
	## now compute IDF for each token in index
	for tok in list(index.keys()):
		index[tok]['idf'] = np.log2(doc_num / len(index[tok]["occ_list"]))
	## finally compute doc lengths
	doc_lengths = { doc_num: 0 for doc_num in all_record_nums }
	for tok in list(index.keys()):
		idf = index[tok]["idf"]
		for doc in index[tok]["occ_list"]:
			occ_count = doc["occ_count"]
			doc_lengths[doc["record_num"]] += (idf * occ_count) ** 2
	for doc_num in list(doc_lengths.keys()):
		doc_lengths[doc_num] = np.sqrt(doc_lengths[doc_num])
	## store computed doc lengths in each record in the index
	for tok in list(index.keys()):
		for word_record in index[tok]['occ_list']:
			word_record['doc_len'] = doc_lengths[word_record["record_num"]]
	return index

ABSTRACT_WEIGHTS = 1
EXTRACT_WEIGHTS = 1
MAJOR_WEIGHTS = 4
MINOR_WEIGHTS = 1
TITLE_WEIGHTS = 2

def format_topics(topics_list, weight):
	new_topic_list = []
	for topic in topics_list:
		curr_topic = topic.lower()
		curr_topic = (curr_topic.replace("-", " "))
		if curr_topic.find(":") > 0 :
			curr_topic = curr_topic[:curr_topic.index(":")]
		new_topic_list.append(curr_topic)
	weighted_topics_list = []
	for i in range(weight):
		for item in new_topic_list:
			weighted_topics_list.append(item)
	return weighted_topics_list



def build_index_v2(path):
	assert os.path.isdir(path)
	files = os.listdir(path)
	xml_files = list(filter(lambda filename: filename.endswith('.xml'), files))
	index = {}
	doc_num = 0
	all_record_nums = []
	for f in xml_files:
		doc = etree.parse(path + '/' + f)
		records = doc.xpath('//RECORD')
		# iterating over the articels
		for r in records:
			doc_num += 1
			record_num = r.xpath('./RECORDNUM/text()')[0].__str__().strip()
			all_record_nums.append(record_num)
			title = r.xpath('./TITLE/text()')
			weighted_title = []
			for token_in_title in title:
				for i in range(TITLE_WEIGHTS):
					weighted_title.append(token_in_title)
			extract = r.xpath('./EXTRACT/text()')
			major_topics = format_topics(r.xpath('./MAJORSUBJ/TOPIC/text()'), MAJOR_WEIGHTS)
			minor_topics = format_topics(r.xpath('./MINORSUBJ/TOPIC/text()'), MINOR_WEIGHTS)
			abstract = r.xpath('./ABSTRACT/text()')
			all_text = ' '.join(weighted_title + extract + abstract + major_topics + minor_topics)
			# all_text = ' '.join(title + extract + abstract)
			words, word_counts = tokenize_v2(all_text)
			max_count = max(list(word_counts.values()))
			for tok in list(word_counts.keys()):
				word_record = {
					'record_num': record_num,
					'occ_count': word_counts[tok],
					'tf': word_counts[tok] / max_count,
				}
				if not tok in index:
					index[tok] = { "occ_list": [word_record] }
				else:
					got = index[tok]
					index[tok]["occ_list"].append(word_record)
			#break
		#break
	## now compute IDF for each token in index
	for tok in list(index.keys()):
		curr_DF = 0
		for occ in index[tok]["occ_list"]:
			curr_DF += int(occ["occ_count"])
		# print("DF:",curr_DF,"current measure:",len(index[tok]["occ_list"]))
		index[tok]['df'] = len(index[tok]["occ_list"])
		index[tok]['idf'] = np.log2(doc_num / len(index[tok]["occ_list"])) # is this the correct way to calculate?
		if tok == "pseudomona":
			print("DF:",curr_DF,"current measure:",len(index[tok]["occ_list"]))

	## finally compute doc lengths
	doc_lengths = { doc_num: 0 for doc_num in all_record_nums }
	for tok in list(index.keys()):
		idf = index[tok]["idf"]
		for doc in index[tok]["occ_list"]:
			# occ_count = doc["occ_count"]
			tf = doc["tf"]
			doc_lengths[doc["record_num"]] += (idf * tf) ** 2
			# doc_lengths[doc["record_num"]] += (idf * occ_count) ** 2
	for doc_num in list(doc_lengths.keys()):
		doc_lengths[doc_num] = np.sqrt(doc_lengths[doc_num])
	## store computed doc lengths in each record in the index
	for tok in list(index.keys()):
		for word_record in index[tok]['occ_list']:
			word_record['doc_len'] = doc_lengths[word_record["record_num"]]
	return index



def query_index_v2(index_path, q):
	index = None
	with open(index_path, 'r') as j:
		index = json.load(j)

	query_toks, tok_counts = tokenize_v2(q)
	found_docs = {}
	doc_lengths = {}
	query_length = 0
	max_token_count = 0
	for tok_count in tok_counts:
		if tok_counts[tok_count] > max_token_count:
			max_token_count = tok_counts[tok_count]
			# print("max token count is:",max_token_count,"for question:",query_toks)
	# going over each token in the query
	for tok in query_toks:
		# if we don't have the token in the index, no need to search for it
		if tok not in index:
			continue
		# print("tok is",tok)
		idf_for_curr_token = index[tok]["idf"] # TODO make sure
		# print("idf for tok ",tok," is:", idf_for_curr_token)
		tf_token_q = tok_counts[tok] / max_token_count
		w_token_q = idf_for_curr_token * tf_token_q  # tf idf
		query_length += w_token_q**2 # check with math as well

		for doc in index[tok]["occ_list"]:
			curr_doc_tf = doc['tf']
			cuur_doc_w = idf_for_curr_token * curr_doc_tf
			if doc["record_num"] not in found_docs:
				found_docs[doc["record_num"]] = 0.0
				doc_lengths[doc["record_num"]] = doc["doc_len"]
			found_docs[doc["record_num"]] += w_token_q * cuur_doc_w
	query_length = np.sqrt(query_length)
	for doc_num in found_docs:
		doc_length = doc_lengths[doc_num]
		found_docs[doc_num] = found_docs[doc_num]/(query_length*doc_length)
	results = sorted(found_docs, key=lambda x: found_docs[x], reverse=True)
	results = [doc for doc in results[0:40] if found_docs[doc] >= 0.08]
	return results





if __name__ == "__main__":
	# print("sys is:", sys.argv)
	# nltk.download('punkt')
	if sys.argv[1] == 'create_index':
		index = build_index_v2(sys.argv[2])
		with open('vsm_inverted_index.json', 'w') as f:
			json.dump(index, f, ensure_ascii=False, indent=4)		# index = build_index_v2('C:/Users/yaire/Desktop/web_data_mgmt/ex4/resources')
	elif sys.argv[1] == 'query':
		# TODO for tester only
		print(sys.argv[3].replace)
		query = sys.argv[3]
		docs = query_index_v2(sys.argv[2], query)

		with open('ranked_query_docs.txt', 'w') as results_file:
			for doc in docs:
				results_file.write(doc+"\n")


