#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Deep neural network architecture
"""

import tensorflow as tf

from keras import backend as K
from keras.models import Sequential
from keras.layers.core import Flatten, Dense, Dropout, Reshape, Lambda
from keras.layers.convolutional import Conv2D, Convolution2D, MaxPooling2D, ZeroPadding2D
from keras.optimizers import SGD
from keras.utils.vis_utils import model_to_dot
from keras.layers.advanced_activations import LeakyReLU
from keras.layers import Input, Dense
from keras.models import Model
from keras.callbacks import TensorBoard, EarlyStopping, ModelCheckpoint

import matplotlib.pyplot as plt
import copy
import cv2, os
import numpy as np

from random import shuffle

from config import *

def normalize_fn(x):
	# return tf.nn.l2_normalize(x, dim=2) # Old for tf 1.x.x
	return tf.nn.l2_normalize(x, axis=2) # Update for tf 2.x.x


def network_arch():

	# Input image shape
	inputs = Input(shape=(224,224,3))
	
	x = Conv2D(64, (3, 3), activation='relu', padding='same', name='block1_conv1')(inputs)
	x = Conv2D(64, (3, 3), activation='relu', padding='same', name='block1_conv2')(x)
	x = MaxPooling2D((2, 2), strides=(2, 2), name='block1_pool')(x)

	x = Conv2D(128, (3, 3), activation='relu', padding='same', name='block2_conv1')(x)
	x = Conv2D(128, (3, 3), activation='relu', padding='same', name='block2_conv2')(x)
	x = MaxPooling2D((2, 2), strides=(2, 2), name='block2_pool')(x)

	x = Conv2D(256, (3, 3), activation='relu', padding='same', name='block3_conv1')(x)
	x = Conv2D(256, (3, 3), activation='relu', padding='same', name='block3_conv2')(x)
	x = Conv2D(256, (3, 3), activation='relu', padding='same', name='block3_conv3')(x)
	x = MaxPooling2D((2, 2), strides=(2, 2), name='block3_pool')(x)

	x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block4_conv1')(x)
	x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block4_conv2')(x)
	x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block4_conv3')(x)
	x = MaxPooling2D((2, 2), strides=(2, 2), name='block4_pool')(x)

	x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv1')(x)
	x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv2')(x)
	x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv3')(x)
	x = MaxPooling2D((2, 2), strides=(2, 2), name='block5_pool')(x)

	x = Flatten()(x)

	dimension   = Dense(512)(x)
	dimension   = LeakyReLU(alpha=0.1)(dimension)
	dimension   = Dropout(0.5)(dimension)
	dimension   = Dense(3)(dimension)
	dimension   = LeakyReLU(alpha=0.1, name='dimension')(dimension)

	orientation = Dense(256)(x)
	orientation = LeakyReLU(alpha=0.1)(orientation)
	orientation = Dropout(0.5)(orientation)
	orientation = Dense(BIN*2)(orientation)
	orientation = LeakyReLU(alpha=0.1)(orientation)
	orientation = Reshape((BIN,-1))(orientation)
	orientation = Lambda(normalize_fn, name='orientation')(orientation)

	confidence  = Dense(256)(x)
	confidence  = LeakyReLU(alpha=0.1)(confidence)
	confidence  = Dropout(0.5)(confidence)
	confidence  = Dense(BIN, activation='softmax', name='confidence')(confidence)

	return Model(inputs, outputs=[dimension, orientation, confidence])

