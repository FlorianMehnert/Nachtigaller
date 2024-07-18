import base64
import io
import os
import random
import sqlite3
import time

import pyperclip
import genanki
import streamlit as st
from PIL import Image

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


def init_db():
    conn = sqlite3.connect('notes.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS notes
                 (question_key TEXT PRIMARY KEY, note_text TEXT, image BLOB)''')
    conn.commit()
    conn.close()


def save_notes():
    conn = sqlite3.connect('notes.db')
    c = conn.cursor()
    for key, value in st.session_state.notes.items():
        c.execute("INSERT OR REPLACE INTO notes (question_key, note_text, image) VALUES (?, ?, ?)",
                  (key, value['text'], value.get('image')))
    conn.commit()
    conn.close()
    st.session_state.saved = True


def load_notes():
    conn = sqlite3.connect('notes.db')
    c = conn.cursor()
    c.execute("SELECT question_key, note_text, image FROM notes")
    notes = {row[0]: {'text': row[1], 'image': row[2]} for row in c.fetchall()}
    conn.close()
    return notes


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


@st.experimental_fragment
def calculate_progress(topics, notes):
    st.write(topics.items())
    total_questions = 0
    answered_questions = 0
    for topic, subtopics in topics.items():
        for subtopic, questions in subtopics.items():
            for i, question in enumerate(questions):
                total_questions += 1
                question_key = f"{topic}_{subtopic}_{i}"
                if question_key in notes and notes[question_key]['text'].strip():
                    answered_questions += 1
    progress_percentage = (answered_questions / total_questions) if total_questions > 0 else 0
    st.title("Progress")
    st.progress(progress_percentage)
    st.write(f"{answered_questions}/{total_questions} questions answered ({progress_percentage * 100:.1f}%)")


# Streamlit app
def main():
    st.title('Markdown Question Parser and Note Taker')

    # Initialize database
    init_db()

    # Initialize session state
    if 'notes' not in st.session_state:
        st.session_state.notes = load_notes()

    if 'topics' not in st.session_state:
        st.session_state.topics = {}

    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0

    if 'saved' not in st.session_state:
        st.session_state.saved = False

    if st.session_state.saved:
        st.toast("saved")
        st.session_state.saved = False


    # File uploader
    uploaded_file = st.file_uploader("Choose a markdown file", type="md")

    if uploaded_file is not None:
        content = uploaded_file.getvalue().decode("utf-8")
        st.session_state.topics = parse_markdown(content)
        with st.sidebar:
            # Calculate and display progress
            calculate_progress(st.session_state.topics, st.session_state.notes)

        # Sidebar for topic selection
        st.sidebar.title("Navigation")
        selected_topic = st.sidebar.selectbox("Select a topic", list(st.session_state.topics.keys()),
                                              key="topic_select")

        # Flatten questions for the selected topic
        all_questions = []
        for subtopic, questions in st.session_state.topics[selected_topic].items():
            all_questions.extend([(subtopic, q) for q in questions])

        # Question selection
        question_options = [f"{i + 1}. {q[1]}" for i, q in enumerate(all_questions)]
        try:
            selected_question_index = st.sidebar.selectbox("Select a question", range(len(question_options)),
                                                           format_func=lambda x: question_options[x],
                                                           index=st.session_state.current_question_index,
                                                           key="question_select")
        except Exception as e:
            selected_question_index = st.sidebar.selectbox("Select a question", range(len(question_options)),
                                                           format_func=lambda x: question_options[x],
                                                           index=0,
                                                           key="question_select")

        # Update current question index
        st.session_state.current_question_index = selected_question_index

        # Navigation buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Previous", on_click=save_notes):
                st.session_state.current_question_index = max(0, st.session_state.current_question_index - 1)
                st.session_state.saved = True
                time.sleep(0.2)
                st.rerun()
        with col3:
            if st.button("Next", on_click=save_notes):
                st.session_state.current_question_index = min(len(all_questions) - 1,
                                                              st.session_state.current_question_index + 1)
                st.session_state.saved = True
                time.sleep(0.2)
                st.rerun()

        # Display current question
        current_subtopic, current_question = all_questions[st.session_state.current_question_index]
        st.header(f"Question {st.session_state.current_question_index + 1}")
        st.subheader(current_subtopic)
        st.write(current_question)
        if st.button("copy"):
            pyperclip.copy(current_question)

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
            image_data = base64.b64decode(existing_image)
            st.image(Image.open(io.BytesIO(image_data)), use_column_width=True)

        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, caption='Newly Uploaded Image', use_column_width=True)

            # Convert image to base64 for storage
            buffered = io.BytesIO()
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            image.save(buffered, format="JPEG", quality=85)
            img_str = base64.b64encode(buffered.getvalue()).decode()

            st.session_state.notes[question_key]['image'] = img_str

        if st.button("Save Notes", on_click=save_notes):
            st.success("Notes saved successfully!")
            calculate_progress(st.session_state.topics, st.session_state.notes)

        # Anki export button
        if st.sidebar.button("Export to Anki"):
            deck, media_files = create_anki_deck(st.session_state.topics, st.session_state.notes)
            deck_filename = "markdown_questions.apkg"
            package = genanki.Package(deck)
            package.media_files = media_files
            package.write_to_file(deck_filename)

            with open(deck_filename, "rb") as file:
                st.sidebar.download_button(
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
