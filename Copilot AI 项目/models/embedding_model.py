from typing import List, Mapping, Set

import numpy as np
import requests
from utils.function_util import timing_decorator
from transformers import AutoTokenizer, AutoModel
import torch
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
import json
from tqdm import tqdm
import math
from sentence_transformers import SentenceTransformer


def list_split(lst, chunk_size=10):
    while True:
        if len(lst) > chunk_size:
            yield lst[:chunk_size]
            lst = lst[chunk_size:]
        else:
            yield lst
            break


# 里程碑3

class EmbeddingModel:
    def __init__(self, model_path):
        self.model_path = model_path
        self.device = torch.device('cpu')
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.embedding_model = AutoModel.from_pretrained(model_path)
        self.embedding_model.eval()
        self.embedding_model.to(self.device)
        self.similarity_model = SentenceTransformer(model_path)
        self.similarity_model.to(self.device)
        self.headers = {'Content-Type': 'application/json'}

    @timing_decorator
    def get_batch_embeddings(self, texts, batch_size=128):
        all_embeddings = []
        chunk_id = 0
        total_chunks = math.ceil(len(texts) / 10)
        for content in list_split(texts, 10):
            chunk_id += 1
            encoded_input = self.tokenizer(content, padding=True, truncation=True, return_tensors='pt')
            if 'token_type_ids' in encoded_input:
                dataset = TensorDataset(encoded_input['input_ids'], encoded_input['attention_mask'],
                                        encoded_input['token_type_ids'])
            else:
                dataset = TensorDataset(encoded_input['input_ids'], encoded_input['attention_mask'])
            dataloader = DataLoader(dataset, batch_size=batch_size)
            lst_embeddings = []
            with torch.no_grad():
                for batch in tqdm(dataloader, desc=f'chunk {chunk_id:02d}/{total_chunks}'):
                    batch = tuple(t.to(self.device) for t in batch)
                    inputs = {'input_ids': batch[0], 'attention_mask': batch[1]}
                    if 'token_type_ids' in encoded_input:
                        inputs['token_type_ids'] = batch[2]

                    model_output = self.embedding_model(**inputs)
                    embeddings = model_output[0][:, 0]  # [CLS] pooling
                    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                    lst_embeddings.append(embeddings)

            lst_embeddings = torch.cat(lst_embeddings, dim=0)
            all_embeddings.extend(lst_embeddings.cpu())

        return all_embeddings

    @timing_decorator
    def get_embedding(self, text):
        encoded_input = self.tokenizer(text, padding=True, truncation=True, return_tensors='pt')

        input_ids = encoded_input['input_ids'].to(self.device)
        attention_mask = encoded_input['attention_mask'].to(self.device)

        if 'token_type_ids' in encoded_input:
            token_type_ids = encoded_input['token_type_ids'].to(self.device)
        else:
            token_type_ids = None

        with torch.no_grad():
            inputs = {'input_ids': input_ids, 'attention_mask': attention_mask}
            if token_type_ids is not None:
                inputs['token_type_ids'] = token_type_ids

            model_output = self.embedding_model(**inputs)
            embedding = model_output[0][:, 0]
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

        return embedding.cpu()

    @timing_decorator
    def get_similarity(self, sentences: List[str], source_sentence: str, recall_num: int = -1,
                       threshold: float = 0):
        text_embeddings = self.similarity_model.encode(sentences)
        query_embedding = self.similarity_model.encode(source_sentence)

        cosine_similarities = np.dot(text_embeddings, query_embedding.T) / (
                np.linalg.norm(text_embeddings, axis=1) * np.linalg.norm(query_embedding))
        sorted_indices = cosine_similarities.argsort()[::-1]

        result_docs = []
        for i in sorted_indices:
            if cosine_similarities[i] > threshold:
                result_docs.append(sentences)
        if recall_num == -1:
            return result_docs
        if len(result_docs) > recall_num:
            return result_docs[0:recall_num]
        else:
            return result_docs
