# YouTube Narratology - a tool for qualitative-quantitative analysis of YouTube shorts

Author: Jill Walker Rettberg / jill.walker.rettberg@uib.no
ORCID: https://orcid.org/0000-0003-2472-3812

## Description
This repository contains code to support qualitative narratological analysis of YouTube shorts and to gather metadata from YouTube to support the analysis, and preliminary data from the analysis. This is a work-in-progress and the annotation system is being developed iteratively as I annotate videos and see which features are most relevant to answer my research questions. This is a small subproject in a larger research project, [AI STORIES: Narrative Archetypes for Artificial Intelligence](https://www4.uib.no/en/research/research-projects/ai-stories). See the [project website](https://www4.uib.no/en/research/research-projects/ai-stories) for more information and a list of other publications and datasets from the project so far.

## Research questions
1. **Which masterplots are most common in AI-generated YouTube shorts?** 

2. **Can Phelan's rhetorical narratology be adapted to work for AI-generated videos?** 
    
    Phelan defines a narrative as a rhetorical action: "Somebody telling somebody else on some occasion and for some purpose(s) that something happened." (See Phelan, James. 2017. 'Somebody telling somebody else', Ohio State UP, page 5). How is this rhetorical act of communication portrayed in the videos themselves? What can the paratext (e.g. video description, hashtags, user comments) tell us about the rhetorical  situation?

3. **When users think the videos are AI-generated, how do they view the "author" or "teller"?** 

## Use of LLMs
I used ChatGPT to help write the code. It often suggested analysis categories, which I usually ignored or at least altered. This README file is partially written using ChatGPT because I figure it's good at structured details like this. I have read and edited the AI-generated bits of the README and have written several parts myself, including this section, the "How to use" section, and the "Research goals".

The full chat where I used ChatGPT to develop the code can be viewed here: https://chatgpt.com/share/6a3ace75-9c20-83ed-a257-541e93d0d590 and before publication I will export the full text of the chat and include it with other documentation.

AI is only used to generate code. No AI is used to generate data or notes. 

## How to use
1. Fork the repository and clone it to your own computer. You have to have the files on your computer to use the local webpage, and you'll probably want to tweak the code to make it do what you want it to do.
2. You'll need to install Flask. 
3. Log into your Google account and get a key for `YouTube Data API v3`. You'll need to [create a project in the Google API Console](https://developers.google.com/youtube/v3/getting-started#:~:text=1,key%2C%20and%20register%20your%20application). Select Credentials -> API key. Save the key somewhere safe. There's a way to save this in your python environment but I haven't yet figured it out so instead I paste this into my terminal window every time I want to run it: `export YOUTUBE_API_KEY="your key here"` with the key between the quotation marks. You'll have to do this again if you restart your computer. 
4. Run app.py from your terminal - this starts the local webpage. Paste this into your terminal: `python3 app.py`. If this process is terminated (if you restart your computer or press Control-C to terminate it or if you change the code in `app.py`) you'll have to do this again. 
5. Open a browser window and put `localhost:9876` as the URL. If you get an error message about the port (the number after `localhost:` edit the code of `app.py`- just find the number and change it to something else.)
6. Use a different browser (one you don't usually use) to view whatever YouTube videos you want to analyse. Watch a video. Paste the URL into the other browser that has the analysing tool running in it. It'll fetch metadata and will give you options to fill out. Hit save and it'll save the metadata and your annotations to `notes.json`.
7. If you want to add the text of comments to the video that mention AI-related words, you can run a different script, `backfill_youtube_metadata_with_comment_text.py`. See below for more on that.

There is also another script, `discover_norwegian_shorts_broad.py`, that uses the YouTube API to search for YouTube shorts that seem Norwegian and looks for AI-related comments. You could edit that to find other kinds of shorts.

## Research goals
This is being developed by Jill Walker Rettberg as part of the AI STORIES project. 

#

* app.py gets the metadata and saves metadata and my notes to notes.json
* templates/index.html is the local webpage I used for annotation - shows an overview of existing notes and metadata for each video I've already annotated and has a search field at the top. When the URL for a new YouTube short is pasted in there it opens the annotation page
* templates/note.html is for the actual annotation. Edit fields that should be shown here, and edit the options for masterplots etc.

## Backfilling metadata for existing notes

Once you have `notes.json` you should run `backfill_youtube_metadata_with_comment_text.py` with the option `--force comments` to update older entries in `notes.json` with missing YouTube metadata and comment analysis. This assumes you already have `notes.json` in the same folder as the script. It creates a backup then writes into your existing notes file.

```bash
python3 backfill_youtube_metadata_with_comment_text.py --force-comments
```
Other options will fetch other metadata if that's missing for some reason. 

The script:
- reads `notes.json`
- creates a timestamped backup in `backedup_notes/`
- fetches missing YouTube metadata
- scans comments for AI-related keywords
- saves updated `notes.json`

### Options

- `--dry-run`  
  Preview which notes would be updated without changing anything.

- `--limit N`  
  Only process the first *N* notes needing updates.

- `--force-comments`  
  Re-scan comments for notes that have AI comment counts but are missing saved comment text.

- `--skip-comments`  
  Skip comment scanning and only fetch metadata.

### Examples

```bash
python3 backfill_youtube_metadata_with_comment_text.py --dry-run
python3 backfill_youtube_metadata_with_comment_text.py --limit 10
python3 backfill_youtube_metadata_with_comment_text.py --force-comments
python3 backfill_youtube_metadata_with_comment_text.py --skip-comments
```
### Variables you might want to change in the script
- `COMMENT_SCAN_LIMIT = 15000`
I used a big number since I wanted to get as many AI-related comments as possible. You can reduce this to save tokens or increase if you're scanning a lot of high-traffic videos and want the detail.

- `AI_COMMENT_WORDS = ["ai", "clanker", "slop", "chatgpt", "fake", "bot", "sora", "nanobanana", "pika", "openai", "luma", "runway", "kling", "llm", "copilot", "gemini", "anthropic", "claude", "generated", "genAI", "synthetic", "deepfake", "glitch", "skvip", "feik"] 

Add or change words here if you like, for example to include other languages or apps. I've included a couple of Norwegian words: skvip is slop and feik is fake.

#### False positives to consider
- "ai" will get false positives for French "j'ai". 
- "fake" will get comments not necessarily about AI, e.g. calling objects (e.g. a wedding ring) fake or saying that the scene is scripted. Might be interesting to include more of these by adding "scripted" to compare accusations of fakeness that are related to AI and not related to AI.
- I tried including "KI" in case that's used in Norwegian content, but "ki" means "that" in some languages.

##Licence
The code is licenced under a CC-BY 4.0 licence. Please reuse or revise in any way that is useful to you. If you use it in an academic publication, please cite this GitHub, and please check back to find associated publications.

##Funding
This project has received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreement number 101142306. The project is also supported by the Center for Digital Narrative, which is funded by the Research Council of Norway through its Centres of Excellence scheme, project number 332643.
