# -*- coding: utf-8 -*-
"""backend_search.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1MJzv5NvIkib3MeQ3O22c8Fhd4UEC1gAi
"""

# !pip install pyspark

# import pyspark
import sys
from collections import Counter, OrderedDict, defaultdict
import itertools
from itertools import islice, count, groupby
import pandas as pd
import os
import re
from operator import itemgetter
import nltk
from nltk.stem.porter import *
from nltk.corpus import stopwords
from time import time
from pathlib import Path
import pickle
import pandas as pd
from google.cloud import storage
# from pyspark import SparkFiles
import math
# from google.cloud import storage
from inverted_index_gcp import *

# authenticate below for Google Storage access as needed
# from google.colab import auth
# auth.authenticate_user()

N = 6348910
bucket_name = 'noa315375998hw3'
# import inverted index body from the bucket
file_path = "id_title_doc.pickle"
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(file_path)
contents = blob.download_as_bytes()
doc_title_doc = pickle.loads(contents)

# import inverted index body from the bucket
file_path = "postings_gcp/index.pkl"
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(file_path)
contents = blob.download_as_bytes()
index_body = pickle.loads(contents)

# import docs length dict from the bucket
file_path = "doclen_dict.pkl"
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(file_path)
contents = blob.download_as_bytes()
doclen_dict = pickle.loads(contents)

# import tfidf title dict from the bucket
file_path = "title_tf_idf.pkl"
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(file_path)
contents = blob.download_as_bytes()
title_tf_idf = pickle.loads(contents)

# import pr scores dict from the bucket
file_path = "pr_dict.pkl"
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(file_path)
contents = blob.download_as_bytes()
pr_dict = pickle.loads(contents)

def read_posting_list(inverted, bucket_name, w, folder_name):
        """
        Read posting list of word from bucket store

        :param w: the requested word
        :param folder_name: name of the folder in the bucket with the bins
        :param bucket_name: name of bucket name
        :param  inverted: inverted index object
        :return posting list - list of tuple (doc_id,tf)

        """
        with closing(MultiFileReader(bucket_name, folder_name)) as reader:
            locs = inverted.posting_locs[w]
            try:
                b = reader.read(locs, inverted.df[w] * 6, bucket_name)
            except:
                return []
            posting_list = []
            for i in range(inverted.df[w]):
                doc_id = int.from_bytes(b[i * 6:i * 6 + 4], 'big')
                tf = int.from_bytes(b[i * 6 + 4:(i + 1) * 6], 'big')
                posting_list.append((doc_id, tf))
            return posting_list

import nltk
nltk.download('stopwords')
english_stopwords = frozenset(stopwords.words('english'))
corpus_stopwords = ["category", "references", "also", "external", "links",
                    "may", "first", "see", "history", "people", "one", "two",
                    "part", "thumb", "including", "second", "following",
                    "many", "however", "would", "became"]

all_stopwords = english_stopwords.union(corpus_stopwords)
RE_WORD = re.compile(r"""[\#\@\w](['\-]?\w){2,24}""", re.UNICODE)

def search_by_text(queryl, index, doclen_dict):
  document_scores = {}
  for term in queryl:
      if term in index.df:
          posting_l = read_posting_list(index, bucket_name, term, "postings_gcp")
          for doc_id, tf in posting_l:
              if doc_id not in document_scores:
                  document_scores[doc_id] = 0
              document_scores[doc_id] += (tf/doclen_dict[doc_id]) * math.log(N/index.df[term])

  # Sort the documents by score in descending order
  ranked_documents = sorted(document_scores.items(), key=lambda x: x[1], reverse=True)

  return ranked_documents[:50]

def calculate_bm25(index, query, k1=1.5, b=0.75):
    scores = defaultdict(float)

    avg_doc_length = sum(doclen_dict.values()) / len(doclen_dict)

    for term in query:
        if term not in index.df.keys():
            continue

        idf = math.log((len(doclen_dict) - index.df[term] + 0.5) / (index.df[term] + 0.5) + 1.0)
        pl = read_posting_list(index, bucket_name, term, "postings_gcp")
        for doc_id, tf in pl:
            doc_length = doclen_dict[doc_id]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_length / avg_doc_length)
            scores[doc_id] += idf * numerator / denominator

    # Convert scores to a list of (doc_id, score) tuples and sort by score
    ranked_documents = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return ranked_documents[:50]

def search_by_title(queryl, title_tf_idf):
  document_scores = {}
  for term in queryl:
      if term in title_tf_idf:
          for doc_id, tf_idf in title_tf_idf[term]:
              if doc_id not in document_scores:
                  document_scores[doc_id] = 0
              document_scores[doc_id] += tf_idf

  # Sort the documents by score in descending order
  ranked_documents = sorted(document_scores.items(), key=lambda x: x[1], reverse=True)

  return ranked_documents[:50]

def search_combined(query, title_weight=0.6, text_weight=0.4):
    # Search by title
    queryl=[token.group() for token in RE_WORD.finditer(query.lower())]
    if len(queryl) <=1:
      title_weight=0.8
      text_weight=0.2
    title_results = search_by_title(queryl, title_tf_idf)

    # Search by text
    text_results = calculate_bm25(index_body, queryl)

    # Combine results with weights
    combined_results = {}

    for doc_id, score in title_results:
      if doc_id in pr_dict.keys():
        combined_results[doc_id] = title_weight * score + math.log(pr_dict[doc_id])
      else:
        combined_results[doc_id] = title_weight * score

    for doc_id, score in text_results:
        if doc_id not in combined_results:
          if doc_id in pr_dict.keys():
            combined_results[doc_id] = math.log(pr_dict[doc_id])
          else:
            combined_results[doc_id] = 0
        combined_results[doc_id] += text_weight * score

    # Sort the combined results by the total score in descending order
    ranked_documents = sorted(combined_results.items(), key=lambda x: x[1], reverse=True)

    res = []

    for doc_id, score in ranked_documents:
        res.append((str(doc_id), doc_title_doc[doc_id]))
    return res[:50]