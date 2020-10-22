#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Train the neural network with KITTI dataset
"""

from keras.optimizers import SGD
import tensorflow as tf
from keras.callbacks import TensorBoard, EarlyStopping, ModelCheckpoint
import copy
import cv2, os
import numpy as np
from random import shuffle

from config import *
import dn_model

def compute_anchors(angle):
	anchors = []
	
	wedge = 2.*np.pi/BIN
	l_index = int(angle/wedge)
	r_index = l_index + 1
	
	if (angle - l_index*wedge) < wedge/2 * (1+OVERLAP/2):
		anchors.append([l_index, angle - l_index*wedge])
		
	if (r_index*wedge - angle) < wedge/2 * (1+OVERLAP/2):
		anchors.append([r_index%BIN, angle - r_index*wedge])
		
	return anchors


def labels_parse(label_dir, image_dir):
	all_objs = []
	dims_avg = {key:np.array([0, 0, 0]) for key in VEHICLE_CLASSES}
	dims_cnt = {key:0 for key in VEHICLE_CLASSES}
		
	for label_file in os.listdir(label_dir):
		image_file = label_file.replace('txt', 'png')

		for line in open(label_dir + label_file).readlines():
			line = line.strip().split(' ')
			truncated = np.abs(float(line[1]))
			occluded  = np.abs(float(line[2]))

			if line[0] in VEHICLE_CLASSES and truncated < 0.1 and occluded < 0.1:
				new_alpha = float(line[3]) + np.pi/2.
				if new_alpha < 0:
					new_alpha = new_alpha + 2.*np.pi
				new_alpha = new_alpha - int(new_alpha/(2.*np.pi))*(2.*np.pi)

				obj = {'name':line[0],
					   'image':image_file,
					   'xmin':int(float(line[4])),
					   'ymin':int(float(line[5])),
					   'xmax':int(float(line[6])),
					   'ymax':int(float(line[7])),
					   'dims':np.array([float(number) for number in line[8:11]]),
					   'new_alpha': new_alpha
					  }
				
				dims_avg[obj['name']]  = dims_cnt[obj['name']]*dims_avg[obj['name']] + obj['dims']
				dims_cnt[obj['name']] += 1
				dims_avg[obj['name']] /= dims_cnt[obj['name']]

				all_objs.append(obj)
			
	return all_objs, dims_avg

all_objs, dims_avg = labels_parse(label_dir, image_dir)

for obj in all_objs:
	# Fix dimensions
	obj['dims'] = obj['dims'] - dims_avg[obj['name']]
	
	# Fix orientation and confidence for no flip
	orientation = np.zeros((BIN,2))
	confidence = np.zeros(BIN)
	
	anchors = compute_anchors(obj['new_alpha'])
	
	for anchor in anchors:
		orientation[anchor[0]] = np.array([np.cos(anchor[1]), np.sin(anchor[1])])
		confidence[anchor[0]] = 1.
		
	confidence = confidence / np.sum(confidence)
		
	obj['orient'] = orientation
	obj['conf'] = confidence
		
	# Fix orientation and confidence for flip
	orientation = np.zeros((BIN,2))
	confidence = np.zeros(BIN)
	
	anchors = compute_anchors(2.*np.pi - obj['new_alpha'])
	
	for anchor in anchors:
		orientation[anchor[0]] = np.array([np.cos(anchor[1]), np.sin(anchor[1])])
		confidence[anchor[0]] = 1
		
	confidence = confidence / np.sum(confidence)
		
	obj['orient_flipped'] = orientation
	obj['conf_flipped'] = confidence


def process_data(train_inst):
	#Crop image
	xmin = train_inst['xmin']
	ymin = train_inst['ymin']
	xmax = train_inst['xmax']
	ymax = train_inst['ymax']
	
	img = cv2.imread(image_dir + train_inst['image'])
	img = copy.deepcopy(img[ymin:ymax+1,xmin:xmax+1]).astype(np.float32)

	# flip the image
	flip = np.random.binomial(1, .5)
	if flip > 0.5: img = cv2.flip(img, 1)
		
	# resize the image and subtract the pixel mean
	img = cv2.resize(img, (NORM_H, NORM_W))
	img = img - np.array([[[103.939, 116.779, 123.68]]])
	
	if flip > 0.5:
		return img, train_inst['dims'], train_inst['orient_flipped'], train_inst['conf_flipped']
	else:
		return img, train_inst['dims'], train_inst['orient'], train_inst['conf']

def generate_data(all_objs, batch_size):
	num_obj = len(all_objs)
	
	keys = range(num_obj)
	np.random.shuffle(keys)
	
	l_bound = 0
	r_bound = batch_size if batch_size < num_obj else num_obj
	
	while True:
		if l_bound == r_bound:
			l_bound  = 0
			r_bound = batch_size if batch_size < num_obj else num_obj
			np.random.shuffle(keys)
		
		currt_inst = 0
		x_batch = np.zeros((r_bound - l_bound, 224, 224, 3))
		d_batch = np.zeros((r_bound - l_bound, 3))
		o_batch = np.zeros((r_bound - l_bound, BIN, 2))
		c_batch = np.zeros((r_bound - l_bound, BIN))
		
		for key in keys[l_bound:r_bound]:
			# augment input image and fix object's orientation and confidence
			image, dimension, orientation, confidence = process_data(all_objs[key])
		   
			x_batch[currt_inst, :] = image
			d_batch[currt_inst, :] = dimension
			o_batch[currt_inst, :] = orientation
			c_batch[currt_inst, :] = confidence
			
			currt_inst += 1
				
		yield x_batch, [d_batch, o_batch, c_batch]
		
		l_bound  = r_bound
		r_bound = r_bound + batch_size
		if r_bound > num_obj: r_bound = num_obj




def orientation_loss(y_true, y_pred):
	# Find number of anchors
	anchors = tf.reduce_sum(tf.square(y_true), axis=2)
	anchors = tf.greater(anchors, tf.constant(0.5))
	anchors = tf.reduce_sum(tf.cast(anchors, tf.float32), 1)
	
	# Define the loss
	loss = -(y_true[:,:,0]*y_pred[:,:,0] + y_true[:,:,1]*y_pred[:,:,1])
	loss = tf.reduce_sum(loss, axis=1)
	loss = loss / anchors
	
	return tf.reduce_mean(loss)



def train_model():
	model = dn_model.network_arch()
	early_stop  = EarlyStopping(monitor='val_loss', min_delta=0.001, patience=10, mode='min', verbose=1)
	checkpoint  = ModelCheckpoint('weights.hdf5', monitor='val_loss', verbose=1, save_best_only=True, mode='min', period=1)
	tensorboard = TensorBoard(log_dir='logs/', histogram_freq=0, write_graph=True, write_images=False)

	all_exams  = len(all_objs)
	trv_split  = int(0.9*all_exams)
	batch_size = 8
	np.random.shuffle(all_objs)

	train_gen = generate_data(all_objs[:trv_split],		  batch_size)
	valid_gen = generate_data(all_objs[trv_split:all_exams], batch_size)

	train_num = int(np.ceil(trv_split/batch_size))
	valid_num = int(np.ceil((all_exams - trv_split)/batch_size))

	minimizer  = SGD(lr=0.0001)
	model.compile(optimizer='adam',#minimizer,
			  loss={'dimension': 'mean_squared_error', 'orientation': orientation_loss, 'confidence': 'mean_squared_error'},
			  loss_weights={'dimension': 1., 'orientation': 1., 'confidence': 1.})
	model.fit_generator(generator = train_gen, 
				steps_per_epoch = train_num, 
				epochs = 500, 
				verbose = 1, 
				validation_data = valid_gen, 
				validation_steps = valid_num, 
				callbacks = [early_stop, checkpoint, tensorboard], 
				# max_q_size = 3) # Old version tf 1.x.x
				max_queue_size = 3) # new version tf 2.x.x

