import streamlit as st
import requests, json, urllib.parse, asyncio, os,base64
from PyPDF2 import PdfReader
from datetime import datetime
import edge_tts
import re
from google import genai
from google.genai import types
import pypdf
import io
import tempfile

# Initialize the Gemini client using your secret key
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
# --- PAGE CONFIG ---
st.set_page_config(page_title="Mantrana AI", page_icon="🪷", layout="centered")

st.markdown("""
    <style>
    /* Force text visible in both modes */
    [data-testid="stChatMessage"] p {
        color: var(--text-color)!important;
    }
    /* Fix for dark mode */
    @media (prefers-color-scheme: dark) {
       .stApp { color: white; }
    }
    /* Make chat input text always visible */
   .stChatInput textarea { color: black!important; }
    </style>
""", unsafe_allow_html=True)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "auto_speak" not in st.session_state:
    st.session_state.auto_speak = True

# --- COMPLETE DARK/LIGHT MODE FIX FOR CHAT + SIDEBAR ---
if st.session_state.dark_mode:
    st.markdown("""
        <style>
        /* App background */
        .stApp { background-color: #0e1117; }
        [data-testid="stSidebar"] { background-color: #151821; }
        
        /* All labels outside boxes - WHITE */
        [data-testid="stSidebar"] label, 
        [data-testid="stSidebar"] h1, h2, h3, p, span {
            color: #ffffff !important;
        }
        
        /* ---- FIX FOR WHITE BOXES ---- */
        /* All inputs with white background = BLACK text inside */
        [data-testid="stSidebar"] input,
        [data-testid="stFileUploader"] *,
        [data-testid="stFileUploader"] button,
        [data-testid="stFileUploader"] div,
        [data-testid="stFileUploader"] p,
        [data-testid="stFileUploader"] span,
        [data-testid="stFileUploader"] small {
            color: #000000 !important;
        }
        
        /* Text input box */
        [data-testid="stTextInput"] input {
            color: #000000 !important;
            background-color: #ffffff !important;
        }
        
        /* Audio input */
        [data-testid="stAudioInput"] * {
            color: #000000 !important;
        }
        [data-testid="stAudioInput"] {
            background-color: #ffffff !important;
        }
        
        /* Buttons - white bg = black text */
        [data-testid="stSidebar"] .stButton button,
        .stDownloadButton button,
        .stButton button {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #cccccc !important;
        }
        [data-testid="stSidebar"] .stButton button p,
        .stButton button p {
            color: #000000 !important;
        }
        
        /* Clear Chat button specific */
        button[kind="secondary"] { 
            color: #000000 !important;
        }
        button[kind="secondary"] p { 
            color: #000000 !important;
        }
        
        /* Chat messages */
        [data-testid="stChatMessage"] p { color: #ffffff !important; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
        .stApp { background-color: #ffffff; }
        h1, h2, h3, h4, p, span, div, label, .stMarkdown {
            color: #000000 !important;
        }
        [data-testid="stChatMessage"] { background-color: #f0f2f6; }
        [data-testid="stChatMessage"] p { color: #000000 !important; }
        
        /* SIDEBAR LIGHT MODE */
        [data-testid="stSidebar"] { background-color: #f8f9fb; }
        [data-testid="stSidebar"] * { color: #000000 !important; }
        [data-testid="stSidebar"] input, 
        [data-testid="stSidebar"] textarea {
            color: #000000 !important;
            background-color: #ffffff !important;
        }
        </style>
    """, unsafe_allow_html=True)

col1, col2 = st.columns([1,5])
with col1:
    try: st.image("logo.png", width=70)
    except: st.markdown("## 🪷")
with col2:
    st.title("Mantrana AI ✨")
    st.caption("मन्त्रणा - Your wise counsel")


if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_image_b64" not in st.session_state:
    st.session_state.last_image_b64 = None
if "last_image_mime" not in st.session_state:
    st.session_state.last_image_mime = None

# --- TTS FUNCTION ---
async def generate_speech(text, voice="en-IN-NeerjaNeural"):
    # Hindi+English mix voice. Change to en-US-AriaNeural for US accent
    # For pure Hindi: hi-IN-SwaraNeural
    clean_text = text[:2000] # limit for speed
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save("mantrana_voice.mp3")

def speak_text(text):
    try:
        # Run async TTS
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Choose voice based on text
        voice = "hi-IN-SwaraNeural" if any(ord(c) > 127 for c in text) else "en-IN-NeerjaNeural"
        loop.run_until_complete(generate_speech(text, voice))
        # Play in streamlit
        st.audio("mantrana_voice.mp3", format="audio/mp3", autoplay=True)
    except Exception as e:
        st.error(f"TTS error: {e}")

# --- SIDEBAR ---
with st.sidebar:
    # --- FIXED FILE READING - STORE IN SESSION ---
    if "file_context" not in st.session_state:
        st.session_state.file_context = ""
    st.markdown("### ⚙️ Controls")
    st.session_state.dark_mode = st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, key="dark_mode_toggle_v1")
    st.session_state.auto_speak = st.toggle("🔊 Auto Speak Answer", value=st.session_state.auto_speak, key="auto_speak_toggle_v1")
    voice_choice = st.selectbox("Voice", ["Neerja - Indian English", "Swara - Hindi", "Aria - US English"], key="voice_select_v1")

    st.divider()
    # FIX 1: Removed st.sidebar. -> just st.file_uploader inside with st.sidebar
    uploaded_file = st.file_uploader("📎 Attach PDF/TXT/CSV", type=["pdf", "txt", "csv"], key="main_file_uploader_v2")

    st.divider()
    uploaded_image = st.file_uploader("🖼️ Attach Image", type=["png","jpg","jpeg"], key="image_uploader_v2")
    if "last_image_b64" not in st.session_state: st.session_state.last_image_b64 = None
    if "last_image_mime" not in st.session_state: st.session_state.last_image_mime = None
    # FIX FOR IMAGE VISION - ADD THIS
    if uploaded_image is not None:
        import base64
        st.image(uploaded_image, caption="Preview", use_container_width=True)
        st.session_state.last_image_b64 = base64.b64encode(uploaded_image.getvalue()).decode()
        st.session_state.last_image_mime = uploaded_image.type

    st.markdown("#### 🎙️ Voice Input")
    audio_value = st.audio_input("Record question", key="audio_input_v2")

    st.divider()
    if st.session_state.messages:
        chat_txt = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
        st.download_button("💾 Download TXT", chat_txt, file_name=f"mantrana_{datetime.now().strftime('%Y%m%d')}.txt", key="dl_txt_v2")
        st.download_button("💾 Download JSON", json.dumps(st.session_state.messages, indent=2), file_name="mantrana.json", key="dl_json_v2")

    if st.button("🗑️ Clear Chat", use_container_width=True, key="clear_chat_v2"):
        st.session_state.messages = []
        st.session_state.last_image_b64 = None
        if os.path.exists("mantrana_voice.mp3"): os.remove("mantrana_voice.mp3")
        st.rerun()
    


# --- ROBUST DOCUMENT READING ---
if uploaded_file is not None:
    try:
        file_name = uploaded_file.name
        file_bytes = uploaded_file.getvalue()
        file_text = ""

        if not file_bytes:
            st.sidebar.error("The uploaded file is empty.")

        elif file_name.lower().endswith(".pdf"):
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))

                if reader.is_encrypted:
                    try:
                        reader.decrypt("")
                    except Exception:
                        raise ValueError(
                            "This PDF is password-protected."
                        )

                extracted_pages = []

                # Read all pages, not just the first 15.
                for page in reader.pages:
                    page_text = page.extract_text(
                        extraction_mode="layout"
                    ) or ""
                    extracted_pages.append(page_text)

                file_text = "\n".join(extracted_pages).strip()

            except Exception as pdf_error:
                st.sidebar.warning(
                    f"Standard PDF extraction failed: {pdf_error}"
                )
                file_text = ""

            # Scanned PDF fallback: ask Gemini to read the PDF itself.
            if not file_text:
                st.sidebar.info(
                    "No selectable text found. Trying Gemini PDF reading..."
                )

                temp_path = None

                try:
                    with tempfile.NamedTemporaryFile(
                        suffix=".pdf", delete=False
                    ) as temp_file:
                        temp_file.write(file_bytes)
                        temp_path = temp_file.name

                    uploaded_pdf = client.files.upload(
                        file=temp_path
                    )

                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=[
                            uploaded_pdf,
                            (
                                "Extract the readable text from this PDF. "
                                "Preserve headings, paragraphs, tables, "
                                "page order, and important details. "
                                "If a page is unreadable, identify it. "
                                "Do not invent missing text."
                            )
                        ]
                    )

                    file_text = (response.text or "").strip()

                finally:
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)

        elif file_name.lower().endswith(".txt"):
            file_text = file_bytes.decode(
                "utf-8-sig", errors="replace"
            ).strip()

        elif file_name.lower().endswith(".csv"):
            import pandas as pd

            df = pd.read_csv(io.BytesIO(file_bytes))
            file_text = df.to_string(index=False).strip()

        # Keep a larger context than the old 15,000-character limit.
        if file_text:
            st.session_state.file_context = file_text[:50000]
            st.session_state.loaded_file_name = file_name

            st.sidebar.success(
                f"Loaded {file_name}: "
                f"{len(file_text)} characters extracted."
            )

            with st.sidebar.expander("Preview document"):
                st.text(file_text[:2000])

            if len(file_text) > 50000:
                st.sidebar.warning(
                    "The extracted document is long; "
                    "only the first 50,000 characters are retained."
                )

        elif file_bytes:
            st.sidebar.error(
                "Could not extract readable text. "
                "The PDF may be damaged, encrypted, or unreadable."
            )

    except Exception as e:
        st.sidebar.error(f"Document reading error: {e}")

# Keep the previously loaded context when no new file is uploaded.
file_context = st.session_state.get("file_context", "")



# Use stored context
file_context = st.session_state.file_context


# --- AUDIO INPUT: GEMINI TRANSCRIPTION ---
voice_prompt = None

if audio_value is not None:
    try:
        with st.spinner("🎙️ Understanding your voice..."):
            audio_bytes = audio_value.getvalue()

            if not audio_bytes:
                st.warning("No audio was recorded. Please try again.")
            else:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[
                        "Transcribe the spoken words exactly as heard. "
                        "Preserve the language spoken, including Hindi or "
                        "English. Return only the transcription.",
                        types.Part.from_bytes(
                            data=audio_bytes,
                            mime_type="audio/wav"
                        )
                    ]
                )

                voice_prompt = (response.text or "").strip()

                if voice_prompt:
                    st.success(f"🎙️ You said: {voice_prompt}")
                else:
                    st.warning(
                        "I could not recognize the speech. "
                        "Please record your question again."
                    )

    except Exception as e:
        st.error(f"Audio transcription error: {e}")


# --- DISPLAY ---
# Display previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["content"].startswith("http"):
            st.image(msg["content"], use_container_width=True)
            st.markdown(f"[📥 Download]({msg['content']})")
        else:
            st.markdown(msg["content"])

def ask_web(prompt_text):
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are Mantrana AI. "
                        "When the user provides a website URL, "
                        "use browser search to access the webpage. "
                        "Read the available webpage content and answer "
                        "the user's question based on that content. "
                        "If the webpage cannot be accessed, clearly say so."
                ),
                tools=[
                    {"url_context": {}},
                    {"google_search": {}}
                ]
            )
        )

        return response.text

    except Exception as e:
        return f"Unable to read the link: {e}"
    
def generate_image(prompt_text):
    try:
        encoded_prompt = urllib.parse.quote(prompt_text)
        pollinations_key = st.secrets.get("POLLINATIONS_API_KEY", "")
        
        # Build the Pollinations endpoint URL with Flux model
        image_url = f"https://gen.pollinations.ai/image/{encoded_prompt}?model=flux"
        if pollinations_key:
            image_url += f"&key={pollinations_key}"
            
        return image_url

    except Exception as e:
        st.error(f"Image generation error: {e}")
        return None

def process_prompt(prompt_text):

    # ============================================================
    # 1. CHECK IF USER HAS UPLOADED AN IMAGE
    # ============================================================

    has_image = (
        st.session_state.get("last_image_b64") is not None
        and st.session_state.get("last_image_mime") is not None
    )


    if has_image:

        st.session_state.messages.append({
        "role": "user",
        "content": prompt_text
    })

        with st.chat_message("user"):
            st.markdown(prompt_text)

        with st.chat_message("assistant"):

            try:
            # Convert stored base64 back into bytes
                image_bytes = base64.b64decode(
                st.session_state.last_image_b64
            )

                mime_type = st.session_state.last_image_mime

            # Create Gemini image part
                image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            )

                response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=[
                    image_part,
                    prompt_text
                ],
                    config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are Mantrana AI, the AI assistant in this application. "
                        "Your name is Mantrana AI. "
                        "Always identify yourself as Mantrana AI. "
                        "Never say that you are ChatGPT. "
                        "Never introduce yourself as ChatGPT. "
                        "Never say that your name is ChatGPT. "
                        "If the user asks who you are, what your name is, "
                        "or asks you to tell them about yourself, "
                        "answer as Mantrana AI. "
                        "You can understand and analyze images. "
                        "Look carefully at the uploaded image and answer "
                        "the user's question based on what you can see. "
                        "If something is unclear or cannot be determined "
                        "from the image, say so honestly."
                    )
                )
            )

                answer = response.text

                st.markdown(answer)

                st.session_state.messages.append({
                "role": "assistant",
                "content": answer
            })

                if st.session_state.get("auto_speak", False):
                    speak_text(answer)

            except Exception as e:
                st.error(f"Image analysis error: {e}")

        return

    # ============================================================
# 2. CHECK FOR WEBSITE LINK
# ============================================================

    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, prompt_text)

    if urls:

        st.session_state.messages.append({
        "role": "user",
        "content": prompt_text
        })

        with st.chat_message("user"):
            st.markdown(prompt_text)

        with st.chat_message("assistant"):

            with st.spinner("🌐 Reading the webpage..."):

                answer = ask_web(prompt_text)

            st.markdown(answer)

        st.session_state.messages.append({
        "role": "assistant",
        "content": answer
        })

        if st.session_state.get("auto_speak", False):
            speak_text(answer)

        return


    # ============================================================
    # 3. IMAGE GENERATION
    # ============================================================

    image_keywords = [
        "generate image",
        "generate an image",
        "create image",
        "create an image",
        "make an image",
        "make image",
        "draw",
        "generate a picture",
        "create a picture",
        "make a picture"
    ]

    prompt_lower = prompt_text.lower()

    if any(keyword in prompt_lower for keyword in image_keywords):

        with st.chat_message("assistant"):

            with st.spinner("🎨 Generating your image..."):

                image_url = generate_image(prompt_text)

                if image_url:
                    st.image(
                        image_url,
                        caption="🎨 Generated by Mantrana AI",
                        use_container_width=True
                    )

                    st.success("✅ Image generated successfully!")
                    st.markdown(f"[📥 Download Image]({image_url})")

        return

    # ============================================================
    # 4. NORMAL TEXT CHAT / DOCUMENT CHAT
    # ============================================================

    current_file_context = st.session_state.get(
        "file_context",
        ""
    )

    if current_file_context:

        final_prompt = f"""
Use this DOCUMENT to answer the user's question.

DOCUMENT CONTENT:
{current_file_context[:50000]}

USER QUESTION:
{prompt_text}

Answer from the document if relevant.
"""

    else:
        final_prompt = prompt_text

    # Save user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt_text
    })

    with st.chat_message("user"):
        st.markdown(prompt_text)

    with st.chat_message("assistant"):

        try:

            chat_history = []

            for m in st.session_state.messages:

                if m["role"] not in ["user", "assistant"]:
                    continue

                # Replace current user message with document-aware prompt
                if m == st.session_state.messages[-1]:

                    chat_history.append({
                        "role": "user",
                        "content": final_prompt
                    })

                else:

                    chat_history.append({
                        "role": m["role"],
                        "content": m["content"]
                    })

            # Keep last 10 messages
            chat_history = chat_history[-10:]

            # Format history for Google GenAI client chats API
            formatted_history = []
            for m in chat_history[:-1]:
                formatted_history.append(
                    types.Content(
                        role="user" if m["role"] == "user" else "model",
                        parts=[types.Part.from_text(text=m["content"])],
                    )
                )

            chat = client.chats.create(
                model="gemini-3.5-flash",
                history=formatted_history,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are Mantrana AI. Give helpful and accurate answers."
                    )
                ),
            )

            try:
                response_stream = chat.send_message_stream(final_prompt)
    # ... stream handling ...
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    st.warning(
            "⚠️ The AI model is currently experiencing high demand. Please try"
            " sending your message again in a moment."
        )
                else:
                    st.error(f"Chat error: {e}")
            def response_generator():
                for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text

            response = st.write_stream(response_generator())

            st.session_state.messages.append({
                "role": "assistant",
                "content": response
            })

            if st.session_state.get("auto_speak", False):
                speak_text(response)

        except Exception as e:
            st.error(f"Chat error: {e}")

if prompt := st.chat_input("Ask Mantrana"):
    process_prompt(prompt)

if voice_prompt:
    process_prompt(voice_prompt)