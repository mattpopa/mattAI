#!/usr/bin/env python3
import os
import sys
import openai
from langchain.document_loaders import (
    TextLoader,
    DirectoryLoader,
)
from langchain.chains import RetrievalQA
from langchain.indexes import VectorstoreIndexCreator
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from IPython.display import display, Markdown
from langchain.vectorstores import DocArrayInMemorySearch

embeddings = OpenAIEmbeddings()

openai.api_key = os.getenv("OPENAI_API_KEY")
query = sys.argv[1]


#file = "OutdoorClothingCatalog_1000.csv"
#loader = CSVLoader(file_path=file)


loader_file = TextLoader('/Users/matt/tmp/serverless/pdf/doc.txt')
loader_pipeline = TextLoader('/Users/matt/tmp/serverless/.github/workflows/pdf-pipeline.yml')

loader_repo_ts = DirectoryLoader('/Users/matt/tmp/serverless/pdf/src', glob="**/*.ts",
                                 loader_cls=TextLoader, use_multithreading=True)
loader_repo_js = DirectoryLoader('/Users/matt/tmp/serverless/pdf', glob="*.js",
                                 loader_cls=TextLoader, use_multithreading=True)
#loader_repo_yml = DirectoryLoader('/Users/matt/tmp/serverless/.github/workflows', glob="*.yml",
#                            loader_cls=TextLoader, use_multithreading=True)

docs_loader_repo_ts = loader_repo_ts.load()
docs_loader_repo_js = loader_repo_js.load()
#docs_loader_repo_yml = loader_repo_yml.load()
docs_loader_repo_yml = loader_pipeline.load()

index = (VectorstoreIndexCreator(vectorstore_cls=DocArrayInMemorySearch).
         from_loaders([loader_file, loader_repo_js, loader_repo_ts, loader_pipeline]))
         #from_loaders([loader_file]))

print("Loaded ts", len(docs_loader_repo_ts))
print("Loaded js", len(docs_loader_repo_js))
#print("Loaded yml", len(docs_loader_repo_js))
print(index.query(query, llm=ChatOpenAI(model_name="gpt-4", temperature=0.0)))
#print(index.query(query))

#response = index.query(query)
#print(response)

#docs = loader.load()
# print(docs[0])

#embed = embeddings.embed_query("Hi my name is Harrison")
#
#print(embed)

# print(len(embed))
# print(embed[:5])

#db = DocArrayInMemorySearch.from_documents(docs, embeddings)

##query = "Please suggest a shirt with sunblocking"
##docs = db.similarity_search(query)
## print(docs[0])
#retriever = db.as_retriever()
#
#llm = ChatOpenAI(model_name="gpt-4", temperature=0.0)
#
##query = ("Please list all your shirts with sun protection in a table "
##         "in markdown and summarize each one.")
#
#query = "what is Harrison"
#response = index.query(query, llm=llm)
#print(response)
