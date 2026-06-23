# YouTube Narratology - a tool for qualitative-quantitative analysis of YouTube shorts

- Author: Jill Walker Rettberg
- Email: jill.walker.rettberg@uib.no
- ORCID: https://orcid.org/0000-0003-2472-3812

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

## Main functions of the scripts
It has three main functions:

1. **Annotate YouTube Shorts manually**
    app.py runs a local Flask web app. You paste a YouTube URL, it fetches metadata via the YouTube Data API, opens an annotation form, and saves metadata + your qualitative notes to `notes.json`. Comment scanning is disabled during ordinary fetches so the form loads quickly. Annotation fields can be edited in `templates/note.html`.
2. **Review and visualize the dataset**
  `templates/index.html` shows saved notes in a sortable table, including automatically fetched metadata such as thumbnails, description, number of comments, channel stats, and AI-related comment text, as well as data that is manually entered by a human such as AI confidence, which (if any) masterplot, a summary of the story, notes about rhetorical features and description of the visuals and audio. The webpage also visualizes masterplots, channel countries, tags, and audio features using Chart.js.
3. **Backfill and discovery scripts**
    Two additional scripts can be run to add the texts of comments with AI-related words to the dataset in `notes.json` and to find videos for analysis.

## Data storage

All annotations are stored in `notes.json`, which is a JSON list where each item represents one annotated video.

Each entry includes:
- YouTube metadata (title, channel, views, comments, etc.)
- channel metadata
- human-coded qualitative annotations

The text of comments containing AI-related words is not initially included but can be added using the script `backfill_youtube_metadata_with_comment_text.py`.

## How to use
1. Fork the repository and clone it to your own computer. You have to have the files on your computer to use the local webpage, and you'll probably want to tweak the code to make it do what you want it to do.
2. You'll need to install Flask. 
3. Log into your Google account and get a key for `YouTube Data API v3`. You'll need to [create a project in the Google API Console](https://developers.google.com/youtube/v3/getting-started#:~:text=1,key%2C%20and%20register%20your%20application). Select Credentials -> API key. Save the key somewhere safe. There's a way to save this in your python environment but I haven't yet figured it out so instead I paste this into my terminal window every time I want to run it: `export YOUTUBE_API_KEY="your key here"` with the key between the quotation marks. You'll have to do this again if you restart your computer. 
4. Run app.py from your terminal - this starts the local webpage. Paste this into your terminal: `python3 app.py`. If this process is terminated (if you restart your computer or press Control-C to terminate it or if you change the code in `app.py`) you'll have to do this again. 
5. Open a browser window and put `localhost:9876` as the URL. If you get an error message about the port (the number after `localhost:` edit the code of `app.py`- just find the number and change it to something else.)
6. Use a different browser (one you don't usually use) to view whatever YouTube videos you want to analyse. Watch a video. Paste the URL into the other browser that has the analysing tool running in it. It'll fetch metadata and will give you options to fill out. Hit save and it'll save the metadata and your annotations to `notes.json`.
7. If you want to add the text of comments to the video that mention AI-related words, you can run a different script, `backfill_youtube_metadata_with_comment_text.py`. See below for more on that.

There is also another script, `discover_norwegian_shorts_broad.py`, that uses the YouTube API to search for YouTube shorts that seem Norwegian and looks for AI-related comments. You could edit that to find other kinds of shorts.

## API quota

The YouTube Data API uses a quota system, so you don't pay, but there is a maximum number of queries a day for each of several different types of query. Fetching basic metadata for each video as you qualitatively code it won't use many queries, and you get 10,000 queries a day. Even fetching comment text doesn't seem to be much of a problem if you're only requesting metadata as fast as you can watch videos as a human. However, you only get 100 'search' queries a day unless you apply for more, so running ``discover_norwegian_shorts_broad.py` and searching through a lot of comments for a lot of videos will use this up fast.

If you receive quota errors, wait until your quota resets or reduce:
- number of videos processed
- comment scan limits
- search pages

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
I used a big number since I wanted to get as many AI-related comments as possible. You can reduce this to save the quota or increase if you're scanning a lot of high-traffic videos and want the detail.

- `AI_COMMENT_WORDS = ["ai", "clanker", "slop", "chatgpt", "fake", "bot", "sora", "nanobanana", "pika", "openai", "luma", "runway", "kling", "llm", "copilot", "gemini", "anthropic", "claude", "generated", "genAI", "synthetic", "deepfake", "glitch", "skvip", "feik"] 

Add or change words here if you like, for example to include other languages or apps. I've included a couple of Norwegian words: skvip is slop and feik is fake.

#### False positives to consider
- "ai" will get false positives for French "j'ai". 
- "fake" will get comments not necessarily about AI, e.g. calling objects (e.g. a wedding ring) fake or saying that the scene is scripted. Might be interesting to include more of these by adding "scripted" to compare accusations of fakeness that are related to AI and not related to AI.
- I tried including "KI" in case that's used in Norwegian content, but "ki" means "that" in some languages.

## Discovering Norwegian Shorts with AI-related comments

The script `discover_norwegian_shorts_broad.py` searches for recent YouTube Shorts that are likely Norwegian and scans their comments for AI-related discussion. The script does **not** determine whether a video is AI-generated, it just identifies some candidates for closer qualitative analysis.

Note that this is not going to give you a representative sample, and there are many ways in which the search terms you pick will skew your sample. The script is suitable if you are looking for examples for qualitative analysis but not if you want to do any kind of statistical analysis. 

Don't use this script to say "x% of Norwegian YouTube shorts are AI-generated - this is not a good enough sampling method for anything like that.

### Requirements

You need a YouTube API key:

```bash
export YOUTUBE_API_KEY="your_key_here"
```

### Basic usage

Run:

```bash
python3 discover_norwegian_shorts_broad.py
```

This searches recent Norwegian-relevant Shorts and saves results to:

```text
discoveries/norwegian_shorts_broad_TIMESTAMP.json
discoveries/norwegian_shorts_broad_TIMESTAMP.csv
```

### Options

- `--days-back N`  
  Search only videos published in the last *N* days (default: 30)

- `--pages N`  
  Number of YouTube search result pages to fetch per search seed  
  (each page returns up to 50 videos)

- `--top-n N`  
  Number of top-viewed candidate videos whose comments will be scanned  
  (default: 100)

- `--min-norwegian-score N`  
  Minimum score required for a video to be considered likely Norwegian

- `--include-broad-seeds`  
  Adds broad Norwegian search terms (such as “Norge” and “norsk”) to expand discovery

### Example

Search the top 100 likely Norwegian Shorts published in the last month:

```bash
python3 discover_norwegian_shorts_broad.py --top-n 100 --days-back 30 --pages 10
```

### Output fields

The exported files include metadata including:
- title
- channel
- upload date
- views
- likes
- comments
- channel statistics
- Norwegian relevance score
- AI-related keywords found in metadata
- number of comments mentioning AI-related terms
- text of matching comments

These results are intended as a discovery dataset for manual qualitative coding.

## Licence
The code is licenced under an MIT license and the data under a CC-BY 4.0 licence. If you use it in an academic publication, please cite this GitHub, and please check back to find associated publications and cite them when available.

## Funding
This project has received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreement number 101142306. The project is also supported by the Center for Digital Narrative, which is funded by the Research Council of Norway through its Centres of Excellence scheme, project number 332643.
