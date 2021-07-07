import os
import sys
import test_queries_parser


def find_unmatched(yours, original):
    missing = []
    additional = []

    for result in original:
        if result not in yours:
            missing.append(result)

    for results in yours:
        if results not in original:
            additional.append(results)

    return missing, additional


queries = test_queries_parser.parse_queries('cfc-xml_corrected')
with open('tester_results_details.txt', 'w') as detailed_results, open('tester_results_aggregated.txt', 'w') as aggregated_results:
    with open('vsm_inverted_index.json', 'r'):
        for q in queries:
            os.system(f'python vsm_ir.py query "{os.getcwd()}\\vsm_inverted_index.json" "{q}"')
            with open('ranked_query_docs.txt', 'r') as results_file:
                your_results = [int(i) for i in results_file]
                original_results = [int(x[0]) for x in q['records']]
                missing, additional = find_unmatched(your_results, original_results)

                if len(missing) != 0 or len(additional) != 0:
                    aggregated_results.write(f'{q["number"]} | missing={len(missing)} | additional={len(additional)} | query={q["text"]} \n')

                detailed_results.write(f'#{q["number"]} {q["text"]} \n'
                                       f'original results = {original_results}\n'
                                       f'your results = {your_results}\n'
                                       f'missing results = {missing}\n'
                                       f'additional results = {additional}\n\n')