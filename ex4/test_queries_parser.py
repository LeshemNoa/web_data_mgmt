import os
import xml.etree.ElementTree as ET


def get_queries_filenames(directory):
    query_xmls = []
    for filename in os.listdir(directory):
        if filename.endswith(".xml") and 'query' in filename:
            query_xmls += [os.path.join(directory, filename)]

    if len(query_xmls) != 1:
        raise Exception('There should be only one query file\n')
    return query_xmls[0]


def parse_single_query(q):
    records = []
    query_text = ''
    number = q.findall("./QueryNumber")[0].text
    results_counter = q.findall("./Results")[0].text
    for text in q.findall("./QueryText"):
        query_text += text.text

    for record in q.findall("./Records"):
        for item in record.findall("./Item"):
            doc = item.text
            raw_score = item.attrib['score']
            records.append((doc, raw_score))

    result = {
        'number': number,
        'text': query_text.replace("\n", ""),
        'results': results_counter,
        'records': records
    }

    return result


def parse_query_file(filename):
    queries = []
    tree = ET.parse(filename)
    root = tree.getroot()
    for q in root:
        queries.append(parse_single_query(q))
    return queries


def parse_queries(directory):
    file = get_queries_filenames(directory)
    return parse_query_file(file)
