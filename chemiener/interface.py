import os
import argparse
from typing import List
import torch
import numpy as np

from .model import build_model

from .dataset import NERDataset, get_collate_fn

from huggingface_hub import hf_hub_download

from .utils import get_class_to_index

class ChemNER:

    def __init__(self, model_path, device = None, cache_dir = None):

        self.args = self._get_args(cache_dir)

        states = torch.load(model_path, map_location = torch.device('cpu'))

        if device is None:
            device = torch.device('cpu')

        self.device = device

        self.model = self.get_model(self.args, device, states['state_dict'])

        self.collate = get_collate_fn()

        self.dataset = NERDataset(self.args, data_file = None)

        self.class_to_index = get_class_to_index(self.args.corpus)

        self.index_to_class = {self.class_to_index[key]: key for key in self.class_to_index}

    def _get_args(self, cache_dir):
        parser = argparse.ArgumentParser()

        parser.add_argument('--roberta_checkpoint', default = 'dmis-lab/biobert-large-cased-v1.1', type=str, help='which roberta config to use')

        parser.add_argument('--corpus', default = "chemdner", type=str, help="which corpus should the tags be from")

        args = parser.parse_args([])

        args.cache_dir = cache_dir

        return args

    def get_model(self, args, device, model_states):
        model = build_model(args)

        def remove_prefix(state_dict):
            return {k.replace('model.', ''): v for k, v in state_dict.items()}

        model.load_state_dict(remove_prefix(model_states), strict = False)

        model.to(device)

        model.eval()

        return model

    def predict_strings(self, strings: List, batch_size = 8):
        device = self.device

        predictions = []

        output = {"sentences": [], "predictions": []}
        for idx in range(0, len(strings), batch_size):
            batch_strings = strings[idx:idx+batch_size]
            batch_strings_tokenized = [(self.dataset.tokenizer(s, truncation = True, max_length = 512),  torch.Tensor([-1]) ) for s in batch_strings]

            sentences, masks, refs = self.collate(batch_strings_tokenized)

            predictions = self.model(input_ids = sentences, attention_mask = masks)[0].argmax(dim = 2).to(device)

            sentences_list = list(sentences)

            predictions_list = list(predictions)

            output["sentences"]+=[ [self.dataset.tokenizer.decode(int(word.item())) for word in sentence if len(self.dataset.tokenizer.decode(int(word.item()), skip_special_tokens = True)) > 0] for sentence in sentences_list]
            output["predictions"]+=[[self.index_to_class[int(pred.item())] for (pred, word) in zip(sentence_p, sentence_w) if len(self.dataset.tokenizer.decode(int(word.item()), skip_special_tokens = True)) > 0] for (sentence_p, sentence_w) in zip(predictions_list, sentences_list)]
        
        return output



            

