import os
from lxml import etree

directory = "cfc-xml_corrected"
path = None
for filename in os.listdir(directory):
    if filename.endswith('query.xml'):
        path = os.path.normpath(os.path.join(directory, filename))
if path is None:
    raise Exception('No query file\n')
xml_tree = etree.parse(path)
with open('tester_results.txt', 'w') as tester_results:
    questions_count = 0
    f_sum = 0
    for query in xml_tree.xpath('//QUERY'):
        questions_count += 1
        query_num = str(int("".join(query.xpath('./QueryNumber/text()'))))
        query_text = "".join(query.xpath('./QueryText/text()')).replace("\n", " ")
        print("query num: ", query_num)
        print("query text: ", query_text)
        query_results = int("".join(query.xpath('./Results/text()')))
        query_records = {}
        for item in query.xpath('./Records/Item'):
            score = "".join(item.xpath('./@score'))
            document = str(int("".join(item.xpath('./text()'))))
            query_records[document] = score
        os.system(f'python vsm_ir.py query "{os.getcwd()}/vsm_inverted_index.json" "{query_text}"')
        with open('ranked_query_docs.txt', 'r') as results_file:
            our_records = [str(int(i)) for i in results_file]
            our_results = len(our_records)
            retrieved_and_relevant_records = [record for record in our_records if record in query_records]
            recall = len(retrieved_and_relevant_records) / query_results
            precision = len(retrieved_and_relevant_records) / our_results
            if recall + precision != 0:
                f_score = (2 * recall * precision) / (recall + precision)
            else:
                f_score = 0
            f_sum += f_score
        tester_results.write(f'{query_num}\n'
                             f'{query_text}\n'
                             f'F-score = {f_score}\n'
                             f'Recall = {recall}\n'
                             f'Precision = {precision}\n'
                             f'Retrieved and Relevant documents: '
                             )
        for record in retrieved_and_relevant_records:
            tester_results.write(f'({record},{query_records[record]}) ')
        tester_results.write("\n\n")
    print("average f_score:", f_sum/questions_count)