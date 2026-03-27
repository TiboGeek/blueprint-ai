import streamlit as st
from openai import OpenAI
from io import BytesIO
from PIL import Image
import base64
import pandas as pd
import json
import re

def markdown_table_to_csv(markdown_text: str) -> pd.DataFrame:
    """
    Converts a valid Markdown table in a given text into a pandas DataFrame.
    It attempts to:
      1) Find continuous lines that start with '|'
      2) Parse the first row as a header
      3) Skip the second "dashes" row
      4) Parse the remaining rows as data
      5) Ensure consistent number of columns
    Raises ValueError if table is not well-formed.
    """
    # Split into lines, strip whitespace
    lines = [line.rstrip() for line in markdown_text.split('\n')]
    # Keep only lines that start with '|' (heuristic for a markdown table row)
    table_lines = []
    for line in lines:
        if line.strip().startswith('|'):
            table_lines.append(line.strip())
    
    # If we didn't find at least 2 lines, there's no valid table
    if len(table_lines) < 2:
        raise ValueError("Could not find a valid markdown table in the provided text.")
    
    # Function to split a line into cells by '|'
    def split_row(row: str):
        # Remove boundary '|' then split on '|'
        row = row.strip('|')
        return [cell.strip() for cell in row.split('|')]
    
    # Parse the header from the first line
    header = split_row(table_lines[0])
    # The second line is typically the dashes line (| --- | --- |)
    # We'll skip it if it contains mostly dashes or is equal in length to header
    data_start_idx = 1
    if len(table_lines) > 1:
        # If it looks like a line of dashes, skip it
        # e.g. set("---- | ----") -> {'-', ' ', '|'}
        dash_chars = set(table_lines[1].replace('|','').replace(' ',''))
        if dash_chars.issubset({'-'}):
            data_start_idx = 2  # skip the second line
    
    # Collect data rows
    data_rows = []
    for row in table_lines[data_start_idx:]:
        cells = split_row(row)
        # If the row doesn't match the number of columns in the header,
        # either skip it or raise an error.
        if len(cells) != len(header):
            # Option 1: Raise an error
            # raise ValueError(f"Row has {len(cells)} cells but header has {len(header)}: {row}")
            
            # Option 2: Skip the malformed row
            continue
        
        data_rows.append(cells)
    
    # Build DataFrame
    if not data_rows:
        raise ValueError("No valid data rows were found in the table.")
    
    return pd.DataFrame(data_rows, columns=header)

st.set_page_config(page_title='Blueprint take-off AI', page_icon='👁️')

st.markdown('# CAD Blueprint take-off AI')
st.markdown('Cette page va extraire les quantités issues des documents')
api_key = st.text_input('OpenAI API Key', '', type='password')

# Get user inputs
img_input = st.file_uploader('Images', accept_multiple_files=True)

# Send API request
if st.button('Send'):
    if not api_key:
        st.warning('API Key required')
        st.stop()
    msg = {'role': 'user', 'content': []}
    msg['content'].append({'type': 'text', 'text': 'Provide a take-off of the quantities from this engineering drawing returning ONLY as a markdown table.'})
    images = []
    for img in img_input:
        if img.name.split('.')[-1].lower() not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
            st.warning('Only .jpg, .png, .gif, or .webp are supported')
            st.stop()
        encoded_img = base64.b64encode(img.read()).decode('utf-8')
        images.append(img)
        msg['content'].append(
            {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{encoded_img}',
                    'detail': 'low'
                }
            }
        )
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model='gpt-4o',
        temperature=0.0,
        max_tokens=300,
        messages=[msg]
    )
    response_msg = str(response.choices[0].message.content)
    # response_msg = 'This is a placeholder response'

    # Display user input and response
    with st.chat_message('user'):
        for i in msg['content']:
            if i['type'] == 'text':
                st.write(i['text'])
            else:
                with st.expander('Attached Image'):
                    img = Image.open(BytesIO(base64.b64decode(i['image_url']['url'][23:])))
                    st.image(img)
    if response_msg:
        with st.chat_message('assistant'):
            st.markdown(response_msg)
             # Assume the entire response_msg is the markdown table
            df = markdown_table_to_csv(response_msg)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download table as CSV",
                data=csv,
                file_name='table.csv',
                mime='text/csv'
            )

            