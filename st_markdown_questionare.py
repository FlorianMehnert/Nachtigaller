import streamlit as st
import json
import os
import genanki
import random
import base64
from PIL import Image
import io


# Function to parse the markdown file
def parse_markdown(content):
    topics = {}
    current_topic = ""
    current_subtopic = ""

    for line in content.split('\n'):
        if line.startswith('## '):
            current_topic = line[3:].strip()
            topics[current_topic] = {}
        elif line.startswith('### '):
            current_subtopic = line[4:].strip()
            topics[current_topic][current_subtopic] = []
        elif line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
            question = line.split('.', 1)[1].strip()
            topics[current_topic][current_subtopic].append(question)

    return topics


# Function to save notes
# Function to save notes
@st.cache_data
def save_notes(notes):
    with open('notes.json', 'w') as f:
        json.dump(notes, f, default=lambda o: o.decode('utf-8') if isinstance(o, bytes) else o)

# Function to load notes
@st.cache_data
def load_notes():
    if os.path.exists('notes.json'):
        with open('notes.json', 'r') as f:
            return json.load(f)
    return {}


# Function to create an Anki deck
def create_anki_deck(topics, notes):
    model = genanki.Model(
        random.randrange(1 << 30, 1 << 31),
        'Question Model',
        fields=[
            {'name': 'Question'},
            {'name': 'Answer'},
            {'name': 'Image'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Question}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}<br>{{Image}}',
            },
        ])

    deck = genanki.Deck(
        random.randrange(1 << 30, 1 << 31),
        'Markdown Questions Deck')

    media_files = []

    for topic, subtopics in topics.items():
        for subtopic, questions in subtopics.items():
            for i, question in enumerate(questions):
                question_key = f"{topic}_{subtopic}_{i}"
                note_data = notes.get(question_key, {})
                note_text = note_data.get('text', "")
                image_data = note_data.get('image')

                image_filename = ''
                if image_data:
                    image_filename = f'image_{question_key}.jpg'
                    with open(image_filename, 'wb') as f:
                        f.write(base64.b64decode(image_data))
                    media_files.append(image_filename)

                anki_note = genanki.Note(
                    model=model,
                    fields=[question, note_text, f'<img src="{image_filename}">' if image_filename else '']
                )
                deck.add_note(anki_note)

    return deck, media_files


# Streamlit app
def main():
    st.title('Markdown Question Parser and Note Taker')

    # Initialize session state
    if 'notes' not in st.session_state:
        st.session_state.notes = load_notes()

    if 'topics' not in st.session_state:
        st.session_state.topics = {}

    # File uploader
    uploaded_file = st.file_uploader("Choose a markdown file", type="md")

    if uploaded_file is not None:
        content = uploaded_file.getvalue().decode("utf-8")
        st.session_state.topics = parse_markdown(content)

        # Sidebar for topic selection
        st.sidebar.title("Navigation")
        selected_topic = st.sidebar.selectbox("Select a topic", list(st.session_state.topics.keys()))

        # Main content area
        st.header(selected_topic)

        for subtopic, questions in st.session_state.topics[selected_topic].items():
            st.subheader(subtopic)
            for i, question in enumerate(questions):
                st.write(f"{i + 1}. {question}")

                # Create a unique key for each question
                question_key = f"{selected_topic}_{subtopic}_{i}"

                # Display existing note or empty string
                existing_note = st.session_state.notes.get(question_key, {}).get('text', "")
                note = st.text_area(f"Notes for question {i + 1}", value=existing_note, key=f"text_{question_key}")

                # Image uploader
                uploaded_image = st.file_uploader(f"Attach image to question {i + 1}", type=['png', 'jpg', 'jpeg'],
                                                  key=f"image_{question_key}")

                if uploaded_image:
                    image = Image.open(uploaded_image)
                    st.image(image, caption='Attached Image', use_column_width=True)

                    # Convert image to base64 for storage
                    buffered = io.BytesIO()
                    image.save(buffered, format="JPEG")
                    img_str = base64.b64encode(buffered.getvalue())

                    st.session_state.notes[question_key] = {'text': note, 'image': img_str}
                else:
                    st.session_state.notes[question_key] = {'text': note,
                                                            'image': st.session_state.notes.get(question_key, {}).get(
                                                                'image')}

        # Save notes button
        if st.button("Save Notes"):
            save_notes(st.session_state.notes)
            st.success("Notes saved successfully!")

        # Anki export button
        if st.sidebar.button("Export to Anki"):
            deck, media_files = create_anki_deck(st.session_state.topics, st.session_state.notes)
            deck_filename = "markdown_questions.apkg"
            package = genanki.Package(deck)
            package.media_files = media_files
            package.write_to_file(deck_filename)

            with open(deck_filename, "rb") as file:
                btn = st.sidebar.download_button(
                    label="Download Anki Deck",
                    data=file,
                    file_name=deck_filename,
                    mime="application/octet-stream"
                )

            st.sidebar.success(f"Anki deck created successfully! Click the button above to download.")

            # Clean up media files
            for file in media_files:
                os.remove(file)


if __name__ == "__main__":
    main()
