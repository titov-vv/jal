import re
import pandas as pd
try:
    import tensorflow as tf
except ImportError:
    pass   # We should not be in this module as dependencies have been checked in slips.py and calls are disabled

from db.helpers import executeSQL, readSQLrecord, readSQL

#----------------------------------------------------------------------------------------------------------------------


def clean_text(text):
    text=re.sub(r'\(.* x .*\)$', '', str(text))   # remove (quantity x price) at the end if it was addded during import
    text = text.lower() + " "                     # lower and add extra space in order not to be cut at end of string
    text=re.sub("^\d*.?:? ?\d* ", "", text)       # drop any leading position numbers in slip and/or product numbers
    text=re.sub(r'\d+ ?шт\b'," QTYPCS ", text)    # replace any quantity in peaces by tag
    text=re.sub(r'\d+ ?к?гр?\b'," QTYWGTH ", text)               # replace any quantity in grams/kilograms by tag
    text=re.sub(r'(\d+(\.|,))?\d+ ?м?(л|l)\b'," QTYVOL ", text)  # replace any quantity in litres/millilitres by tag
    text=re.sub(r'(\d+(\.|,))?\d+ ?(с|м)?м\b'," SIZE ", text)    # replace any quantity in legth units by tag
    text=re.sub(r'(\d+(\.|,))?\d+ ?%(?P<tail>\W)'," PERCENT \g<tail>", text)  # replace percentages by tag
    text=re.sub(r'\b\d+((\.|,)\d+)?\b', " NUMBER ", text)        # put numbers as tags
    text = re.sub(r'\.|\,|\"|\#|\*|\=|\+|\(|\)'," ", text)       # Remove punctuation (keep '-', '/')
    text = re.sub(r'\s\S\s', " ", text)            # remove any single separate standing non-space character
    return text

#----------------------------------------------------------------------------------------------------------------------


def recognize_categories(db, purchases):
    used_classes_number = readSQL(db, "SELECT COUNT(DISTINCT mapped_to) AS cnt FROM map_category")

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
    tokenizer = tf.keras.preprocessing.text.Tokenizer(num_words=5000, oov_token='UNKNOWN', lower=False)
    tokenizer.fit_on_texts(descriptions)
    dictionary_size = len(tokenizer.word_index)
    descriptions_sequenced = tokenizer.texts_to_sequences(descriptions)
    max_desc_len = len(max(descriptions_sequenced, key=len))
    X = tf.keras.preprocessing.sequence.pad_sequences(descriptions_sequenced, padding='post', maxlen=max_desc_len)

    # prepare Y values
    Y = tf.keras.utils.to_categorical(data.mapped_to)
    classes_number = Y.shape[1]

    # prepare and train model
    nn_model = tf.keras.Sequential(
        [tf.keras.layers.Embedding(input_length=max_desc_len, input_dim=dictionary_size + 1, output_dim=50),
         tf.keras.layers.Flatten(),
         tf.keras.layers.Dense(used_classes_number + 1, activation='relu'),
         tf.keras.layers.Dense(used_classes_number + 1, activation='relu'),
         tf.keras.layers.Dense(classes_number, activation='softmax')
         ])
    nn_model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
    nn_model.fit(X, Y, epochs=40, batch_size=50, verbose=0)

    # predict categories
    purchases_sequenced = tokenizer.texts_to_sequences(purchases)
    NewX = tf.keras.preprocessing.sequence.pad_sequences(purchases_sequenced, padding='post', maxlen=max_desc_len)
    NewY = nn_model.predict(NewX)
    result = tf.keras.backend.argmax(NewY, axis=1)
    probability = NewY.max(axis=1)

    return result.numpy().tolist(), probability.tolist()