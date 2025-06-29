import os
from pathlib import Path

from langchain.schema import Document
from langchain_community.document_loaders.pdf import PyPDFDirectoryLoader
from langchain_community.vectorstores.chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_PATH = "chroma"
DATA_PATH = "data"
CHUNK_SIZE = 750
CHUNK_OVERLAP = 100


def get_embeddings():
    model_kwargs = {'device': 'cpu'}  # 'cuda'
    embeddings_hf = HuggingFaceEmbeddings(
        model_name='intfloat/multilingual-e5-large',
        model_kwargs=model_kwargs
    )
    return embeddings_hf


def load_documents():
    loader = PyPDFDirectoryLoader(DATA_PATH, glob="*.pdf")
    documents = loader.load()
    return documents


def split_text(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Разбили {len(documents)} документов на {len(chunks)} чанков.")

    return chunks


def save_to_chroma(chunks: list[Document]):
    # Clear out the database first.
    if os.path.exists(CHROMA_PATH):
        # shutil.rmtree(CHROMA_PATH)
        print(f"CHROMA_PATH is existing")
    else:
        print(f"CHROMA_PATH is not existing, creating new")
        Path(CHROMA_PATH).mkdir(exist_ok=True)
    # Create a new DB from the documents.
    db = Chroma.from_documents(
        chunks, get_embeddings(), persist_directory=CHROMA_PATH
    )
    db.persist()
    print(f"Saved {len(chunks)} chunks to {CHROMA_PATH}.")


if __name__ == "__main__":
    documents = load_documents()
    chunks = split_text(documents)
    save_to_chroma(chunks)
