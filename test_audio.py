import streamlit as st

st.title("🎙️ Microphone Test")

audio = st.audio_input(
    "🎙️ Record something",
    sample_rate=16000
)

if audio is not None:
    st.success("✅ Recording received!")

    st.audio(audio)

    st.write("Audio type:", audio.type)
    st.write("Audio size:", len(audio.getvalue()), "bytes")