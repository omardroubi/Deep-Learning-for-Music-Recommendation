import os

import numpy as np
import sklearn
from sklearn import metrics
import pandas as pd

import keras
from keras.models import load_model
from keras import backend as K
from keras.utils import to_categorical

import h5py
import pickle

import argparse

import warnings
warnings.filterwarnings("ignore")

import FMA

parser = argparse.ArgumentParser(description="gets testing results from a model")
parser.add_argument('-d', '--dataset', required=True, help='dataset to use: fma_med, fma_large')
parser.add_argument('-t', '--test', default='', help='test to carry out: single genre classification (sgc). multi genre classification (mgc)')
parser.add_argument('-f', '--features', default='', help='features to use: stft, stft_halved, mel_scaled_stft, cqt, chroma, mfcc')
args = parser.parse_args()

class DataGenerator(keras.utils.Sequence):
    'Generates data for Keras'
    def __init__(self, list_IDs, labels, batch_size, dim, n_classes, features, dataset, test_type, shuffle=True):
        'Initialization'
        self.list_IDs = list_IDs
        self.labels = labels
        self.batch_size = batch_size
        self.dim = dim
        self.n_classes = n_classes
        self.features = features
        self.dataset = dataset
        self.data_path = './Data/features/' + dataset + '_' + features + '.hdf5'
        self.test_type = test_type
        self.shuffle = shuffle
        self.on_epoch_end()

    def __len__(self):
        'Denotes the number of batches per epoch'
        return int(np.floor(len(self.list_IDs) / self.batch_size))

    def __getitem__(self, index):
        'Generate one batch of data'
        # Generate indexes of the batch
        indexes = self.indexes[index*self.batch_size:(index+1)*self.batch_size]

        # Find list of IDs
        list_IDs_temp = [self.list_IDs[k] for k in indexes]

        # Generate data
        X, y = self.__data_generation(list_IDs_temp)

        return X, y

    def on_epoch_end(self):
        'Updates indexes after each epoch'
        self.indexes = np.arange(len(self.list_IDs))
        if self.shuffle == True:
            np.random.shuffle(self.indexes)

    def __data_generation(self, list_IDs_temp):
        'Generates data containing batch_size samples' 
        X = np.empty((self.batch_size, self.dim[1], self.dim[0]))

        if self.test_type == 'sgc':
            y = np.empty((self.batch_size), dtype=int)
        if self.test_type == 'mgc':
            y = np.empty((self.batch_size, self.n_classes), dtype=int)

        with h5py.File(self.data_path,'r') as f:
            for i, ID in enumerate(list_IDs_temp):
                X[i,] = f['data'][str(ID)]
                if self.test_type == 'sgc':
                    y[i] = self.labels[ID]
                if self.test_type == 'mgc':
                    y[i,:] = self.labels[ID]
            
        if self.test_type == 'sgc':
            return X.reshape(X.shape[0], *self.dim), keras.utils.to_categorical(y, num_classes=self.n_classes)
        elif self.test_type == 'mgc':
            return X.reshape(X.shape[0], *self.dim), y

def test_model_sgc(model_name, dim, features, dataset):
    K.clear_session()
    
    model_path = './Models/rnn/sgc/' + dataset + '.' + features + '.' + model_name + '.hdf5'

    model = load_model(model_path)

    if dataset == 'fma_med':
        test_list = FMA.PARTITION['test']
        labels = FMA.TOP_GENRES
        num_classes = FMA.NUM_CLASSES

        tbs = 1
        for i in range(1,17):
            if len(test_list) % i == 0:
                tbs = i
        
        test_generator = DataGenerator(
            list_IDs=test_list,
            labels=labels,
            batch_size=tbs,
            dim=dim,
            n_classes=num_classes,
            features=features,
            dataset=dataset,
            test_type='sgc',
            shuffle=False
        )

        softmax_out = model.predict_generator(
            generator=test_generator,
            verbose=1
        )


    predicted = []
    for pred in softmax_out:
        predicted.append(pred.argmax())
    
    predicted = np.array(predicted)

    acc = sum(predicted == y_true) / len(predicted)
    f1_macro = metrics.f1_score(y_true, predicted, average='macro')
    f1_micro = metrics.f1_score(y_true, predicted, average='micro')
    f1_weighted = metrics.f1_score(y_true, predicted, average='weighted')
    
    print(f'{model_path}\nacc {acc:.5f} f1_macro {f1_macro:.5f} f1_micro {f1_micro:.5f} f1_weighted {f1_weighted:.5f}\n')
    
    return softmax_out, acc, f1_macro, f1_micro, f1_weighted

def test_model_mgc(model_name, dim, features, dataset):
    K.clear_session()
    
    model_path = './Models/rnn/mgc/' + dataset + '.' + features + '.' + model_name + '.hdf5'

    model = load_model(model_path)

    if dataset == 'fma_large':
        test_list = FMA.PARTITION['test']
        labels = FMA.ALL_GENRES
        num_classes = FMA.NUM_CLASSES

        tbs = 1
        for i in range(1,17):
            if len(test_list) % i == 0:
                tbs = i
        
        test_generator = DataGenerator(
            list_IDs=test_list,
            labels=labels,
            batch_size=tbs,
            dim=dim,
            n_classes=num_classes,
            features=features,
            dataset=dataset,
            test_type='mgc',
            shuffle=False
        )

        sigmoid_out = model.predict_generator(
            generator=test_generator,
            verbose=1
        )

    predicted = np.asarray(np.around(sigmoid_out), dtype=np.int)

    hamm = metrics.hamming_loss(y_true, predicted)
    mse = np.mean((y_true - sigmoid_out)**2)

    print(f'{model_path}\nhamm {hamm:.6f} mse {mse:.6f}')
    
    return sigmoid_out, hamm, mse

if __name__ == '__main__':
    if args.dataset in ['fma_med', 'fma_large']:
        if args.features == 'stft':
            freq, time = 2049, 643  
            dim = (time, freq)

        if args.features == 'stft_halved':
            freq, time = 2049//2, 643
            dim = (time, freq)

        if args.features == 'mel_scaled_stft':
            freq, time = 256, 643
            dim = (time, freq)

        if args.features == 'cqt':
            freq, time = 168, 643
            dim = (time, freq)

        if args.features in ['chroma', 'mfcc']:
            freq, time = 12, 643
            dim = (time, freq)
        
        if args.dataset == 'fma_med':
            FMA = FMA.FreeMusicArchive('medium', 22050)

            y_true = []
            for i in FMA.PARTITION['test']:
                y_true.append(FMA.TOP_GENRES[i])

            y_true = np.array(y_true)    
            y_true_oh = keras.utils.to_categorical(y_true, num_classes=FMA.NUM_CLASSES)
        
        if args.dataset == 'fma_large':
            FMA = FMA.FreeMusicArchive('large', 22050)

            y_true = []
            for i in FMA.PARTITION['test']:
                y_true.append(FMA.ALL_GENRES[i])

            y_true = np.array(y_true)
            y_true_oh = y_true

    else:
        raise Exception('Wrong dataset!')

    if args.test == 'sgc':
        results = pd.DataFrame({
            'name':['RNN']
        })

        hist_path = './Models/rnn/' + args.test + '/' + args.dataset + '.' + args.features + '.' + 'RNN' + '.history.pkl'
        hist=pickle.load(open(hist_path, "rb" ))

        results['hist_acc'] = [hist['categorical_accuracy']]
        results['hist_val_acc'] = [hist['val_categorical_accuracy']]
        results['epochs'] = len(hist['categorical_accuracy'])
    

        sm, acc, macro, micro, weighted = test_model_sgc(model_name='RNN', dim=dim, features=args.features, dataset=args.dataset)

        results['accuracy'] = acc 
        results['f1_macro'] = macro
        results['f1_micro'] = micro
        results['f1_weighted'] = weighted
        results['softmax_out'] = [sm] 

        save_path = './Results/rnn/' + args.test + '/' + args.dataset + '.' + args.features  + '.pkl'

        results.to_pickle(save_path)

    if args.test == 'mgc':
        results = pd.DataFrame({
            'name':['RNN']
        })

        hist_path = './Models/rnn/' + args.test + '/' + args.dataset + '.' + args.features + '.' + 'RNN' + '.history.pkl'
        hist=pickle.load(open(hist_path, "rb" ))

        results['hist_cat_acc'] = [hist['categorical_accuracy']]
        results['hist_bin_acc'] = [hist['binary_accuracy']]
        results['hist_mse'] = len(hist['mean_squared_error'])
        results['hist_val_loss'] = len(hist['val_loss'])
        results['epochs'] = len(hist['categorical_accuracy'])

        sig_out, h, m = test_model_mgc(model_name='RNN', dim=dim, features=args.features, dataset=args.dataset)

        results['hamm'] = h
        results['mse'] = m
        results['sigmoid_out'] = [sig_out] 

        save_path = './Results/rnn/' + args.test + '/' + args.dataset + '.' + args.features  + '.pkl'

        results.to_pickle(save_path)