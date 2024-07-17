import streamlit as st
import json
import os
import genanki
import random
import base64
from PIL import Image
import io
import datetime
import time
from io import BytesIO


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


def calculate_progress(topics, notes):
    total_questions = 0
    answered_questions = 0
    for topic, subtopics in topics.items():
        for subtopic, questions in subtopics.items():
            for i, question in enumerate(questions):
                total_questions += 1
                question_key = f"{topic}_{subtopic}_{i}"
                if question_key in notes and notes[question_key].get('text', '').strip():
                    answered_questions += 1
    return answered_questions, total_questions


# Streamlit app
def main():
    st.title('Markdown Question Parser and Note Taker')

    # Initialize session state
    if 'notes' not in st.session_state:
        st.session_state.notes = load_notes()

    if 'topics' not in st.session_state:
        st.session_state.topics = {}

    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0

    # File uploader
    uploaded_file = st.file_uploader("Choose a markdown file", type="md")

    if uploaded_file is not None:
        content = uploaded_file.getvalue().decode("utf-8")
        st.session_state.topics = parse_markdown(content)

        # Calculate and display progress
        answered, total = calculate_progress(st.session_state.topics, st.session_state.notes)
        progress_percentage = (answered / total) if total > 0 else 0
        st.sidebar.title("Progress")
        st.sidebar.progress(progress_percentage)
        st.sidebar.write(f"{answered}/{total} questions answered ({progress_percentage * 100:.1f}%)")

        # Sidebar for topic selection
        st.sidebar.title("Navigation")
        selected_topic = st.sidebar.selectbox("Select a topic", list(st.session_state.topics.keys()), key="topic_select")

        # Flatten questions for the selected topic
        all_questions = []
        for subtopic, questions in st.session_state.topics[selected_topic].items():
            all_questions.extend([(subtopic, q) for q in questions])

        # Question selection
        question_options = [f"{i+1}. {q[1]}" for i, q in enumerate(all_questions)]
        selected_question_index = st.sidebar.selectbox("Select a question", range(len(question_options)),
                                                       format_func=lambda x: question_options[x],
                                                       index=st.session_state.current_question_index,
                                                       key="question_select")

        # Update current question index
        st.session_state.current_question_index = selected_question_index

        # Navigation buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Previous"):
                st.session_state.current_question_index = max(0, st.session_state.current_question_index - 1)
                st.experimental_rerun()
        with col3:
            if st.button("Next"):
                st.session_state.current_question_index = min(len(all_questions) - 1, st.session_state.current_question_index + 1)
                st.experimental_rerun()

        # Display current question
        current_subtopic, current_question = all_questions[st.session_state.current_question_index]
        st.header(f"Question {st.session_state.current_question_index + 1}")
        st.subheader(current_subtopic)
        st.write(current_question)

        # Create a unique key for the current question
        question_key = f"{selected_topic}_{current_subtopic}_{st.session_state.current_question_index}"

        # Initialize the question key in the notes if it doesn't exist
        if question_key not in st.session_state.notes:
            st.session_state.notes[question_key] = {'text': '', 'image': None}

        # Display existing note or empty string
        existing_note = st.session_state.notes[question_key]['text']
        note = st.text_area("Notes", value=existing_note, key=f"text_{question_key}")

        # Update the note text
        st.session_state.notes[question_key]['text'] = note

        # Image uploader
        uploaded_image = st.file_uploader("Attach image", type=['png', 'jpg', 'jpeg'], key=f"image_{question_key}")

        # Display existing image if available
        existing_image = st.session_state.notes[question_key].get('image')
        if existing_image:
            st.image(Image.open(io.BytesIO(base64.b64decode(existing_image))), caption='Attached Image', use_column_width=True)

        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, caption='Newly Uploaded Image', use_column_width=True)

            # Convert image to base64 for storage
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue())

            st.session_state.notes[question_key]['image'] = img_str

        # Save notes button
        if st.button("Save Notes"):
            save_notes(st.session_state.notes)
            st.success("Notes saved successfully!")
            st.experimental_rerun()  # Rerun to update progress bar

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
