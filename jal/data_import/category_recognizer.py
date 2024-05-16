import re
import pandas as pd
from jal.db.category import JalCategory

#----------------------------------------------------------------------------------------------------------------------


def clean_text(text):
    text=re.sub(r"\(.* x .*\)$", "", str(text))   # remove (quantity x price) at the end if it was addded during import
    text = text.lower() + " "                     # lower and add extra space in order not to be cut at end of string
    text=re.sub(r"^\d*.?:? ?\d* ", "", text)       # drop any leading position numbers in slip and/or product numbers
    text=re.sub(r"\d+ ?шт\b"," QTYPCS ", text)    # replace any quantity in peaces by tag
    text=re.sub(r"\d+ ?к?гр?\b"," QTYWGTH ", text)               # replace any quantity in grams/kilograms by tag
    text=re.sub(r"(\d+(\.|,))?\d+ ?м?(л|l)\b"," QTYVOL ", text)  # replace any quantity in litres/millilitres by tag
    text=re.sub(r"(\d+(\.|,))?\d+ ?(с|м)?м\b"," SIZE ", text)    # replace any quantity in legth units by tag
    text=re.sub(r"(\d+(\.|,))?\d+ ?%(?P<tail>\W)",r" PERCENT \g<tail>", text)  # replace percentages by tag
    text=re.sub(r"\b\d+((\.|,)\d+)?\b", " NUMBER ", text)        # put numbers as tags
    text = re.sub(r"\.|\,|\"|\#|\*|\=|\+|\(|\)"," ", text)       # Remove punctuation (keep "-", "/")
    text = re.sub(r"\s\S\s", " ", text)            # remove any single separate standing non-space character
    return text

#----------------------------------------------------------------------------------------------------------------------


def recognize_categories(purchases):
    import tensorflow as tf
    import tensorflow.keras as keras
    tf.get_logger().setLevel('WARNING')

    classes_number = 0
    classes = []
    mapped_values = JalCategory.get_mapped_names()
    for category in set([x['mapped_to'] for x in mapped_values]):  # set() is used to get unique list from full list
        classes.append({
            'idx': classes_number,
            'category': category
        })
        classes_number += 1
    categories = pd.DataFrame(classes)

    data = pd.DataFrame(mapped_values)
    data = data.merge(categories, left_on="mapped_to", right_on='category')
    data = data.drop(columns=['mapped_to', 'category'])     # we don't need this column as we will use custom 'idx'

    data['cleaned_value'] = data.value.apply(clean_text)

    # prepare X values
    descriptions = data.cleaned_value
    tokenizer = keras.preprocessing.text.Tokenizer(num_words=5000, oov_token='UNKNOWN', lower=False)
    tokenizer.fit_on_texts(descriptions)
    dictionary_size = len(tokenizer.word_index)
    descriptions_sequenced = tokenizer.texts_to_sequences(descriptions)
    max_desc_len = len(max(descriptions_sequenced, key=len))
    X = keras.preprocessing.sequence.pad_sequences(descriptions_sequenced, padding='post', maxlen=max_desc_len)

    # prepare Y values
    Y = keras.utils.to_categorical(data.idx)

    # prepare and train model
    nn_model = keras.Sequential(
        [keras.layers.Embedding(input_length=max_desc_len, input_dim=dictionary_size + 1, output_dim=classes_number * 2),
         keras.layers.Flatten(),
         keras.layers.Dense(classes_number * 4, activation='relu'),
         keras.layers.Dense(classes_number, activation='softmax')
         ])
    nn_model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
    nn_model.fit(X, Y, epochs=40, batch_size=50, verbose=0)

    # predict categories
    purchases_sequenced = tokenizer.texts_to_sequences(purchases)
    NewX = keras.preprocessing.sequence.pad_sequences(purchases_sequenced, padding='post', maxlen=max_desc_len)
    NewY = nn_model.predict(NewX)
    result_idx = keras.backend.argmax(NewY, axis=1)
    result = categories.take(result_idx.numpy().tolist()).category
    probability = NewY.max(axis=1)

    return result.tolist(), probability.tolist()