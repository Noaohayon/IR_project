# IR_project

List of files:
index_dict_creation.ipynb - this file contains all the creation of our indexes and dictionaries converted into pickles. For the text index we calculated additional dictionaries such as document length.
backend_search.py - this file containes some of the helper functions we used for our main search function in the file 'search_frontend.py'.
inverted_index_gcp.py - this file containes the InvertedIndex class that keeps the global dictionaries of our index. in addition to that it containes the classes MultiFileWriter and MultiFileReader that write/read to/from to the memory.
search_frontend.py - this file containes all of the search functions we created.

The main search function:
In our main search function the data from out index moves throw several stages until we reach a final list of documents that we return.

The first step in our function is tokenizing the query and removeing stopwords/ terms that are not in our index.
we determined weigths for our combine function. 
If the query is only one word we give a higher weight to the title and if the query is longer than a word we give a higher weigth to the text of the document.
We calculate similarity between the text of the document and the query using inner product and the weigths are tf-idf. We return from the function only the documents that their similarity score is the highest.
We calculate the similarity between the query and the document's title using inner product similarity.
We use a combine function to merge the results of the similarity with the title and the text according to the weigths we determined. We return from the function only the documents that their merged scores are the top 50.
We map between the doc id and the Title of the document and return a tuples list.
