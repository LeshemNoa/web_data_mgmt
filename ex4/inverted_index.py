from lxml import etree
import os, string, re, json
import numpy as np
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

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
	return words, word_counts

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
			words, word_counts = tokenize(all_text)
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


def query_index(q, index):
	query_toks, tok_counts = tokenize(q)
	found_docs = {}
	query_length = 0
	for tok in query_toks:
		if not tok in index:
			continue
		idf = index[tok]["idf"] 
		query_tok_weight = tok_counts[tok] * idf
		query_length += query_tok_weight ** 2
		for word_record in index[tok]["occ_list"]:
			doc_num = word_record["record_num"]
			if not doc_num in found_docs:
				found_docs[doc_num] = { "score": 0, "doc_len": word_record["doc_len"] }
			found_docs[doc_num]["score"] += query_tok_weight * idf * word_record["tf"]
	query_length = np.sqrt(query_length)
	for doc_num in found_docs:
		score = found_docs[doc_num]["score"]
		doc_len = found_docs[doc_num]["doc_len"]
		found_docs[doc_num] = score / (doc_len * query_length)
	result = sorted(found_docs, key=found_docs.get)
	return result

if __name__ == "__main__":
	index = build_index('./ex4/resources')
	# with open('./ex4/inverted_index.json', 'w') as f:
	# 	json.dump(index, f, ensure_ascii=False, indent=4)
	q = "What congenital or hereditary diseases or conditions have been found in association with CF?"
	docs = query_index(q, index)
	print(docs)
	