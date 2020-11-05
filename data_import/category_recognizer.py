import re
import pandas as pd
try:
    import tensorflow as tf
except ImportError:
    pass   # We should not be in this module as dependencies have been checked in slips.py and calls are disabled

from db.helpers import executeSQL, readSQLrecord

#----------------------------------------------------------------------------------------------------------------------


def clean_text(text):
    # Remove non-alphanumeric
    text=re.sub("\W"," ", str(text))
    # Remove digits
    text = re.sub("\d"," ", text)
    return text

#----------------------------------------------------------------------------------------------------------------------


def recognize_categories(db, purchases):
    # Load data from DB into pandas dataframe
    query = executeSQL(db, "SELECT value, mapped_to FROM map_category")
    table = []
    while query.next():
        value, mapped_to = readSQLrecord(query)
        table.append({
            'value': value,
            'mapped_to': mapped_to
        })
    data = pd.DataFrame(table)

    data['cleaned_value'] = data.value.apply(clean_text)

    # prepare X values
    descriptions = data.cleaned_value
    tokenizer = tf.keras.preprocessing.text.Tokenizer(num_words=5000, oov_token='XXXXXXX')
    tokenizer.fit_on_texts(descriptions)
    dictionary_size = len(tokenizer.word_index)
    descriptions_sequenced = tokenizer.texts_to_sequences(descriptions)
    X = tf.keras.preprocessing.sequence.pad_sequences(descriptions_sequenced, padding='post', maxlen=64)

    # prepare Y values
    Y = tf.keras.utils.to_categorical(data.mapped_to)
    classes_number = Y.shape[1]

    # prepare and train model
    nn_model = tf.keras.Sequential(
        [tf.keras.layers.Embedding(input_length=64, input_dim=dictionary_size + 1, output_dim=50),
         tf.keras.layers.Flatten(),
         tf.keras.layers.Dense(100, activation='relu'),
         tf.keras.layers.Dense(classes_number, activation='softmax')
         ])
    nn_model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
    nn_model.fit(X, Y, epochs=50, batch_size=50, verbose=0)

    # predict categories
    purchases_sequenced = tokenizer.texts_to_sequences(purchases)
    NewX = tf.keras.preprocessing.sequence.pad_sequences(purchases_sequenced, padding='post', maxlen=64)
    NewY = nn_model.predict(NewX)
    result = tf.keras.backend.argmax(NewY, axis=1)

    return result.numpy().tolist()