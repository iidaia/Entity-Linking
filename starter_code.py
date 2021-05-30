import gzip
from bs4 import BeautifulSoup
import en_core_web_sm
import trident
from operator import itemgetter
import sys
import json
from elasticsearch import Elasticsearch

KEYNAME = "WARC-Record-ID"

def search(query):
    e = Elasticsearch(["fs0.das5.cs.vu.nl"], port=10010, timeout=30, max_retries=10, retry_on_timeout=True)
    p = { "query" : { "query_string" : { "query" : query }}}
    response = e.search(index="wikidata_en", body=json.dumps(p))
    id_labels = {}
    if response:
        for hit in response['hits']['hits']:
            label = hit['_source']['schema_name']
            id = hit['_id']
            id_labels.setdefault(id, set()).add(label)
    return id_labels

# The goal of this function process the webpage and returns a list of labels -> entity ID
def find_labels(payload):
    
    if payload == '':
        return

    # The variable payload contains the source code of a webpage and some additional meta-data.
    # We firt retrieve the ID of the webpage, which is indicated in a line that starts with KEYNAME.
    # The ID is contained in the variable 'key'
    key = None
    for line in payload.splitlines():
        if line.startswith(KEYNAME):
            key = line.split(': ')[1]
            break    
    

    # Problem 1: The webpage is typically encoded in HTML format.
    # We should get rid of the HTML tags and retrieve the text. How can we do it?    
    
    soup = BeautifulSoup(payload, 'html.parser')
    
    if not "Content-Type: text/html; charset=UTF-8" in soup.text:
        
        return
    else: 
        
        headers, body = soup.text.split("Content-Type: text/html; charset=UTF-8")

    rawtext = body.strip() 
    rawtext = rawtext.split("\n")
    non_empty_lines = [line for line in rawtext if line.strip() != ""]

    text = ""
    for line in non_empty_lines:
        text += line + " "
        
    # sys.stdout.write(text)
        
    # Problem 2: Let's assume that we found a way to retrieve the text from a webpage. How can we recognize the
    # entities in the text?
  
    nlp = en_core_web_sm.load()
    doc = nlp(text)   
    
    # Problem 3: We now have to disambiguate the entities in the text. For instance, let's assugme that we identified
    # the entity "Michael Jordan". Which entity in Wikidata is the one that is referred to in the text?
    
    KBPATH='assets/wikidata-20200203-truthy-uri-tridentdb'
    db = trident.Db(KBPATH)
    result_list = []
    
    for entity in doc.ents:
        
        search_list = search(entity.text).items()
        pop_list = []

        for item in search_list:
            
            reference = db.lookup_id(item[0])
            pop = db.count_o(reference)
            pop_list.append((item[0], pop))
            
        pop_list.sort(key=itemgetter(1), reverse=True)
    
        result_list.append((key, entity.label_, pop_list[0][0]))
    
    
    for row in result_list:
        
        yield row[0], row[1], row[2]
        
    # To tackle this problem, you have access to two tools that can be useful. The first is a SPARQL engine (Trident)
    # with a local copy of Wikidata. The file "test_sparql.py" shows how you can execute SPARQL queries to retrieve
    # valuable knowledge. Please be aware that a SPARQL engine is not the best tool in case you want to lookup for
    # some strings. For this task, you can use elasticsearch, which is also installed in the docker image.
    # The file start_elasticsearch_server.sh will start the elasticsearch server while the file
    # test_elasticsearch_server.py shows how you can query the engine.

    # A simple implementation would be to first query elasticsearch to retrieve all the entities with a label
    # that is similar to the text found in the web page. Then, you can access the SPARQL engine to retrieve valuable
    # knowledge that can help you to disambiguate the entity. For instance, if you know that the webpage refers to persons
    # then you can query the knowledge base to filter out all the entities that are not persons...

    # Obviously, more sophisticated implementations that the one suggested above are more than welcome :-)    
       

    # For now, we are cheating. We are going to returthe labels that we stored in sample-labels-cheat.txt
    # Instead of doing that, you should process the text to identify the entities. Your implementation should return
    # the discovered disambiguated entities with the same format so that I can check the performance of your program.
    # cheats = dict((line.split('\t', 2) for line in open('data/sample-labels-cheat.txt').read().splitlines()))
    # for label, wikidata_id in cheats.items():
    #     if key and (label in payload):
    #         yield key, label, wikidata_id
    


def split_records(stream):
    payload = ''
    for line in stream:
        if line.strip() == "WARC/1.0":
            yield payload
            payload = ''
        else:
            payload += line
    yield payload

if __name__ == '__main__':
    import sys
    try:
        _, INPUT = sys.argv
    except Exception as e:
        print('Usage: python starter-code.py INPUT')
        sys.exit(0)

    with gzip.open(INPUT, 'rt', errors='ignore') as fo:
        i = 0
        for record in split_records(fo):
            i += 1
            if i == 4:
                break
            else:
                for key, label, wikidata_id in find_labels(record):
                    print(key + '\t' + label + '\t' + wikidata_id)
