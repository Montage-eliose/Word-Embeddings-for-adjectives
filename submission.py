## Submission.py for COMP6714-Project2
###################################################################################################################

import os
import math
import random
import zipfile
import numpy as np
import tensorflow as tf
import collections
import gensim
import spacy
import sys
#from os import walk
#from gensim import utils, matutils


def isNoise(token):	
	is_noise=False
	if token.is_alpha!=True:
		is_noise = True
	#elif token.is_stop == True:
		#is_noise = True
	return is_noise
	'''     
    if token.pos_ in noisy_pos_tags:
        is_noise = True
    elif token.is_stop == True:
        is_noise = True
    elif len(token.string) <= min_token_length:
        is_noise = True
    '''
    #return is_noise
def cleanup(token, lower = True):
    if lower:
       token = token.lower()
    return token.strip()

data_index = 0 
# the variable is abused in this implementation. 
# Outside the sample generation loop, it is the position of the sliding window: from data_index to data_index + span
# Inside the sample generation loop, it is the next word to be added to a size-limited buffer. 

def generate_batch(batch_size, num_samples, skip_window,data,reverse_dictionary):
    global data_index   
    
    assert batch_size % num_samples == 0
    assert num_samples <= 2 * skip_window
    
    batch = np.ndarray(shape=(batch_size), dtype=np.int32)
    labels = np.ndarray(shape=(batch_size, 1), dtype=np.int32)
    span = 2 * skip_window + 1  # span is the width of the sliding window
    buffer = collections.deque(maxlen=span)
    if data_index + span > len(data):
        data_index = 0
    buffer.extend(data[data_index:data_index + span]) # initial buffer content = first sliding window
    
    #print('data_index = {}, buffer = {}'.format(data_index, [reverse_dictionary[w] for w in buffer]))

    data_index += span
    for i in range(batch_size // num_samples):
        context_words = [w for w in range(span) if w != skip_window]
        random.shuffle(context_words)
        words_to_use = collections.deque(context_words) # now we obtain a random list of context words
        for j in range(num_samples): # generate the training pairs
            batch[i * num_samples + j] = buffer[skip_window]
            context_word = words_to_use.pop()
            labels[i * num_samples + j, 0] = buffer[context_word] # buffer[context_word] is a random context word
        
        # slide the window to the next position    
        if data_index == len(data):
            buffer = data[:span]
            data_index = span
        else: 
            buffer.append(data[data_index]) # note that due to the size limit, the left most word is automatically removed from the buffer.
            data_index += 1
        
        #print('data_index = {}, buffer = {}'.format(data_index, [reverse_dictionary[w] for w in buffer]))
        
    # end-of-for
    data_index = (data_index + len(data) - span) % len(data) # move data_index back by `span`
    return batch, labels


def adjective_embeddings(data_file, embeddings_file_name, num_steps, embedding_dim):
	pass # Remove this pass line, you need to implement your code for Adjective Embeddings here...
	vocabulary_size=17000#004-----
	data, count, dictionary, reverse_dictionary = build_dataset(data_file,vocabulary_size)
	# del vocabulary  # No longer used, helps in saving space...
	#print('Most common words (+UNK)', count[:5])
	#print('Sample data', data[:10], [reverse_dictionary[i] for i in data[:10]])

	
	batch_size = 128      # Size of mini-batch for skip-gram model.
	embedding_size = 200  # Dimension of the embedding vector.
	skip_window = 1       # How many words to consider left and right of the target word.
	num_samples = 2         # How many times to reuse an input to generate a label.
	num_sampled = 128      # Sample size for negative examples.
	logs_path = './log/'

	# Specification of test Sample:
	sample_size = 20       # Random sample of words to evaluate similarity.
	sample_window = 100    # Only pick samples in the head of the distribution.
	sample_examples = np.random.choice(sample_window, sample_size, replace=False) # Randomly pick a sample of size 16

	## Constructing the graph...
	graph = tf.Graph()

	with graph.as_default():
    
	    with tf.device('/cpu:0'):
	        # Placeholders to read input data.
	        with tf.name_scope('Inputs'):
	            train_inputs = tf.placeholder(tf.int32, shape=[batch_size])
	            train_labels = tf.placeholder(tf.int32, shape=[batch_size, 1])
	            
	        # Look up embeddings for inputs.
	        with tf.name_scope('Embeddings'):            
	            sample_dataset = tf.constant(sample_examples, dtype=tf.int32)
	            embeddings = tf.Variable(tf.random_uniform([vocabulary_size, embedding_size], -1.0, 1.0))
	            embed = tf.nn.embedding_lookup(embeddings, train_inputs)
	            
	            # Construct the variables for the NCE loss
	            nce_weights = tf.Variable(tf.truncated_normal([vocabulary_size, embedding_size],
	                                                      stddev=1.0 / math.sqrt(embedding_size)))
	            nce_biases = tf.Variable(tf.zeros([vocabulary_size]))
	        
	        # Compute the average NCE loss for the batch.
	        # tf.nce_loss automatically draws a new sample of the negative labels each
	        # time we evaluate the loss.
	        with tf.name_scope('Loss'):
	            loss = tf.reduce_mean(tf.nn.sampled_softmax_loss(weights=nce_weights, biases=nce_biases, 
	                                             labels=train_labels, inputs=embed, 
	                                             num_sampled=num_sampled, num_classes=vocabulary_size))
	        
	        # Construct the Gradient Descent optimizer using a learning rate of 0.01.
	        with tf.name_scope('Adam'):
	            optimizer = tf.train.AdamOptimizer(learning_rate = 0.001).minimize(loss)

	        # Normalize the embeddings to avoid overfitting.
	        with tf.name_scope('Normalization'):
	            norm = tf.sqrt(tf.reduce_sum(tf.square(embeddings), 1, keep_dims=True))
	            normalized_embeddings = embeddings / norm
	            
	        sample_embeddings = tf.nn.embedding_lookup(normalized_embeddings, sample_dataset)
	        similarity = tf.matmul(sample_embeddings, normalized_embeddings, transpose_b=True)
	        
	        # Add variable initializer.
	        init = tf.global_variables_initializer()
	        
	        
	        # Create a summary to monitor cost tensor
	        tf.summary.scalar("cost", loss)
	        # Merge all summary variables.
	        merged_summary_op = tf.summary.merge_all()


	with tf.Session(graph=graph) as session:
    # We must initialize all variables before we use them.
	    session.run(init)
	    summary_writer = tf.summary.FileWriter(logs_path, graph=tf.get_default_graph())
	    
	    print('Initializing the model')
	    
	    average_loss = 0
	    for step in range(num_steps):
	        batch_inputs, batch_labels = generate_batch(batch_size, num_samples, skip_window,data,reverse_dictionary)
	        feed_dict = {train_inputs: batch_inputs, train_labels: batch_labels}
	        
	        # We perform one update step by evaluating the optimizer op using session.run()
	        _, loss_val, summary = session.run([optimizer, loss, merged_summary_op], feed_dict=feed_dict)
	        
	        summary_writer.add_summary(summary, step )
	        average_loss += loss_val

	        if step % 5000 == 0:
	            if step > 0:
	                average_loss /= 5000
	            
	                # The average loss is an estimate of the loss over the last 5000 batches.
	                print('Average loss at step ', step, ': ', average_loss)
	                average_loss = 0

	        # Evaluate similarity after every 10000 iterations.
	        if step % 10000 == 0:
	            sim = similarity.eval() #
	            for i in range(sample_size):
	                sample_word = reverse_dictionary[sample_examples[i]]
	                top_k = 10  # Look for top-10 neighbours for words in sample set.
	                nearest = (-sim[i, :]).argsort()[1:top_k + 1]
	                log_str = 'Nearest to %s:' % sample_word
	                for k in range(top_k):
	                    close_word = reverse_dictionary[nearest[k]]
	                    log_str = '%s %s,' % (log_str, close_word)
	                print(log_str)
	            print()
	            
	    final_embeddings = normalized_embeddings.eval()


	#total_vec=vocabulary_size
	vector_size=embedding_size
	nlp = spacy.load('en')
	total_vec=0
	with gensim.utils.smart_open(embeddings_file_name, 'wb') as fout:
		for j in range(vocabulary_size):
			doc=nlp(reverse_dictionary[j])
			if doc[0].pos_=="ADJ":
				total_vec+=1
				#print(total_vec)
		fout.write(gensim.utils.to_utf8("%s %s\n" % (total_vec, vector_size)))
		for i in range(vocabulary_size):
			row=final_embeddings[i]
			doc=nlp(reverse_dictionary[i])
			#if reverse_dictionary[i]=="chief":
				#print("yes")
			if doc[0].pos_=="ADJ":
				fout.write(gensim.utils.to_utf8("%s %s\n" % (reverse_dictionary[i], ' '.join("%f" % val for val in row))))


	    #for i in range(5):
	    #	print (reverse_dictionary[i],final_embeddings[i])
	   
	
	#with utl


def process_data(input_data):
	data=[]
	#words=[]
	nlp = spacy.load('en')
	with zipfile.ZipFile(input_data,'r') as f:
		for i in range(0,len(f.namelist())):
		#for i in range(0,5):
			doc=tf.compat.as_str(f.read(f.namelist()[i])).split()
			#print(doc)
			#for word in tmp:
			#	if word.lower().strip().isalpha():
			#		data.extend(word)
			#doc=nlp(tf.compat.as_str(f.read(f.namelist()[i])))
			#print(i)
			cleaned_list = [cleanup(word) for word in doc if word.isalpha()]
			#cleaned_list = [cleanup(word.string) for word in doc if not isNoise(word)]
			data.extend(cleaned_list)
	#print("data",len(data))
	with open('data_file','w') as fout:
		fout.write(str(data))
	fileobj='data_file'
	return fileobj
	pass# Remove this pass line, you need to implement your code to process data here...

def build_dataset(words,vocabulary_size):
    """Process raw inputs into a dataset. 
       words: a list of words, i.e., the input data
       n_words: Vocab_size to limit the size of the vocabulary. Other words will be mapped to 'UNK'
    """
    #vocabulary_size=len(collections.Counter(words))
    #if 
    tmpwords=[]
    with open (words,'r') as fread:
    	for line in fread:
    		tmpwords.extend(line.replace('[','').replace(']','').replace("'",'').replace(" ",'').split(','))
    #print(len(tmpwords))
    count = [['UNK', -1]]
    count.extend(collections.Counter(tmpwords).most_common(vocabulary_size - 1))
    dictionary = dict()
    for word, _ in count:
        dictionary[word] = len(dictionary)
    data = list()
    unk_count = 0
    for word in tmpwords:
        index = dictionary.get(word, 0)
        if index == 0:  # i.e., one of the 'UNK' words
            unk_count += 1
        data.append(index)
    count[0][1] = unk_count
    #print("data2",len(data))
    reverse_dictionary = dict(zip(dictionary.values(), dictionary.keys()))
    return data, count, dictionary, reverse_dictionary

def Compute_topk(model_file, input_adjective, top_k):
    pass # Remove this pass line, you need to implement your code to compute top_k words similar to input_adjective
    result=[]
    model = gensim.models.KeyedVectors.load_word2vec_format(model_file, binary=False)
    if input_adjective in model.wv.vocab:
    	tmp=model.wv.most_similar(positive=input_adjective,topn=top_k)
    	for i in tmp:
    		result.append(i[0])
    return result

'''

def read_dic(dic_path):
    dev_adjectives = []
    Synonyms = {}
    for (dirpath, dirnames, filenames) in walk(dic_path):
        dev_adjectives.extend(filenames)
    dev_adjectives.remove('.DS_Store')
    for filename in dev_adjectives:
    	if (filename!=".DS_Store"):
        	with open(os.path.join(dic_path, filename), 'r') as infile:
        		#print(filename)
        		syn = [line.strip() for line in infile]
        	Synonyms[filename] = syn
    return Synonyms, dev_adjectives


def Compute_Hits(adjective, output_list, Synonyms):
    synonym_list = Synonyms.get(adjective)
    result = 0.0
    for word in output_list:
        if (word in synonym_list):
            result = result + 1
    return result


part1 = None
part3 = None
part3 = None
input_dir = './BBC_Data.zip'
data_file = process_data(input_dir)
if(os.path.isfile(data_file)):
        print('Writing Processed Data file(Success)\n')
        part1 = 1
else:
        print('Writing Processed Data file(Failed)\n')
data, count, dictionary, reverse_dictionary = build_dataset(data_file,17000)
print(data_file,len(data))

# del vocabulary  # No longer used, helps in saving space...
print('Most common words (+UNK)', count[:5])
print('Sample data', data[:10], [reverse_dictionary[i] for i in data[:10]])
print('data[0:10] = {}'.format([reverse_dictionary[i] for i in data[:10]]))
print('\n.. First batch')
batch, labels = generate_batch(batch_size=8, num_samples=2, skip_window=1)
for i in range(8):
    print(reverse_dictionary[batch[i]], '->', reverse_dictionary[labels[i, 0]])
print(data_index)
    
print('\n.. Second batch')
batch, labels = generate_batch(batch_size=8, num_samples=2, skip_window=1)
for i in range(8):
    print(reverse_dictionary[batch[i]], '->', reverse_dictionary[labels[i, 0]])
print(data_index)
'''
'''
embedding_file_name = 'adjective_embeddings.txt'
## Fixed parameters
#num_steps = 100001
num_steps=10
embedding_dim = 200
adjective_embeddings(data_file, embedding_file_name, num_steps, embedding_dim)

if(os.path.isfile('./adjective_embeddings.txt')):
        print('Writing Embedding file(Success)\n')
        part2 = 1
else:
        print('Writing Embedding file(Failed)\n')
        '''

'''
defaultencoding = 'utf-8'
if sys.getdefaultencoding() != defaultencoding:
    reload(sys)
    sys.setdefaultencoding(defaultencoding)
'''
'''
top_k = 100
model_file = './adjective_embeddings.txt'
Synonyms, dev_adjectives = read_dic('./dev_set')
print('Reading Trained Model')
if (os.path.isfile('./adjective_embeddings.txt')):
	total_hits = []
	#print("test")
	for adjective in dev_adjectives:
		#print(adjective)
		output_list = Compute_topk(model_file, adjective, top_k)
		hits = Compute_Hits(adjective, output_list, Synonyms)
		total_hits.append(hits)
		result = np.average([x for x in total_hits])
		part3 = 1
	print('Reading Trained Model(Success)')
	print('Average Hits on Dev Set is = %f ' %(result))
else:
	print('Reading Trained Model(Failure)\n')

result = [part1, part2, part3]
for item in result:
	if item == None:
		print('Error Please check your code')





i) Abstract/Summary
ii) Introduction
iii) Methodology
iv) Results and Discussion
v) Conclusion
	'''