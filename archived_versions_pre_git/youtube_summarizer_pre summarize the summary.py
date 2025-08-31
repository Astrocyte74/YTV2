#!/usr/bin/env python3
"""
YouTube Video Summarizer using MCP-Use Library
Extracts transcripts from YouTube videos and generates intelligent summaries
"""

import asyncio
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import yt_dlp

# Try to import youtube-transcript-api for better transcript access
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    print("⚠️  youtube-transcript-api not available, will use yt-dlp only")
    TRANSCRIPT_API_AVAILABLE = False
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.llms import Ollama
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage
import requests

# Import LLM configuration manager
from llm_config import llm_config

class YouTubeSummarizer:
    def __init__(self, llm_provider: str = None, model: str = None, ollama_base_url: str = None):
        """Initialize the YouTube Summarizer with mkpy LLM integration
        
        Args:
            llm_provider: Optional override for LLM provider. If None, uses mkpy configuration
            model: Optional override for model. If None, uses mkpy configuration  
            ollama_base_url: Base URL for Ollama server (default from config)
        """
        self.downloads_dir = Path("./downloads")
        self.downloads_dir.mkdir(exist_ok=True)
        
        # Get LLM configuration from mkpy system
        try:
            self.llm_provider, self.model, api_key = llm_config.get_model_config(llm_provider, model)
        except ValueError as e:
            print(f"🔴 {e}")
            raise
        
        # Set Ollama base URL
        self.ollama_base_url = ollama_base_url or llm_config.ollama_host
        
        # Initialize LLM based on determined configuration
        self._initialize_llm(api_key)
    
    def _initialize_llm(self, api_key: str):
        """Initialize the LLM based on provider and model"""
        
        if self.llm_provider == "openai":
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=api_key
            )
        elif self.llm_provider == "anthropic":
            self.llm = ChatAnthropic(
                model=self.model,
                api_key=api_key
            )
        elif self.llm_provider == "openrouter":
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://github.com/astrocyte74/stuff",
                    "X-Title": "YouTube Summarizer"
                }
            )
        elif self.llm_provider == "ollama":
            self.llm = ChatOllama(
                model=self.model,
                base_url=self.ollama_base_url
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
    
    def _extract_video_id(self, youtube_url: str) -> str:
        """Extract video ID from YouTube URL"""
        if 'watch?v=' in youtube_url:
            return youtube_url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in youtube_url:
            return youtube_url.split('youtu.be/')[1].split('?')[0]
        elif '/embed/' in youtube_url:
            return youtube_url.split('/embed/')[1].split('?')[0]
        else:
            # Assume it's already a video ID
            return youtube_url
    
    def _get_transcript_via_api(self, video_id: str) -> Optional[str]:
        """Extract transcript using youtube-transcript-api (primary method)"""
        if not TRANSCRIPT_API_AVAILABLE:
            return None
            
        try:
            api = YouTubeTranscriptApi()
            transcript_data = api.fetch(video_id)
            
            # Extract text from the transcript snippets
            if hasattr(transcript_data, 'snippets'):
                text_parts = [snippet.text for snippet in transcript_data.snippets]
                full_text = ' '.join(text_parts)
                print(f"✅ YouTube Transcript API: Extracted {len(full_text)} characters")
                return full_text
            else:
                print(f"⚠️  YouTube Transcript API: Unexpected response format")
                return None
                
        except Exception as e:
            print(f"⚠️  YouTube Transcript API failed: {e}")
            return None
    
    def _try_yt_dlp_transcript_extraction(self, info: dict) -> Optional[str]:
        """Try to extract transcript using yt-dlp as fallback method"""
        transcript_text = ""
        
        try:
            # Check for automatic captions first - try multiple English variants
            english_keys = ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU']
            auto_caps = None
            
            if 'automatic_captions' in info:
                for lang_key in english_keys:
                    if lang_key in info['automatic_captions']:
                        auto_caps = info['automatic_captions'][lang_key]
                        print(f"🔍 yt-dlp fallback: Found {len(auto_caps)} automatic caption formats in {lang_key}")
                        break
            
            if auto_caps:
                for cap in auto_caps:
                    if cap.get('ext') in ['srv3', 'json3', 'ttml', 'vtt']:
                        transcript_url = cap['url']
                        try:
                            import urllib.request
                            with urllib.request.urlopen(transcript_url) as response:
                                transcript_data = response.read().decode('utf-8')
                                if cap.get('ext') == 'srv3':
                                    transcript_text = self._parse_srv3_transcript(transcript_data)
                                else:
                                    transcript_text = self._parse_generic_transcript(transcript_data)
                                
                                if transcript_text.strip():
                                    print(f"✅ yt-dlp fallback: Extracted via {cap.get('ext')} format")
                                    return transcript_text
                        except Exception as e:
                            print(f"⚠️  yt-dlp fallback error: {e}")
            
            # Try manual subtitles if auto captions failed
            if 'subtitles' in info and 'en' in info['subtitles']:
                manual_subs = info['subtitles']['en']
                print(f"🔍 yt-dlp fallback: Trying {len(manual_subs)} manual subtitle formats")
                for sub in manual_subs:
                    if sub.get('ext') in ['srv3', 'json3', 'ttml', 'vtt']:
                        try:
                            import urllib.request
                            with urllib.request.urlopen(sub['url']) as response:
                                transcript_data = response.read().decode('utf-8')
                                if sub.get('ext') == 'srv3':
                                    transcript_text = self._parse_srv3_transcript(transcript_data)
                                else:
                                    transcript_text = self._parse_generic_transcript(transcript_data)
                                
                                if transcript_text.strip():
                                    print(f"✅ yt-dlp fallback: Extracted via manual {sub.get('ext')} format")
                                    return transcript_text
                        except Exception as e:
                            print(f"⚠️  yt-dlp fallback error: {e}")
            
            return transcript_text if transcript_text.strip() else None
            
        except Exception as e:
            print(f"⚠️  yt-dlp transcript extraction failed: {e}")
            return None
    
    def extract_transcript(self, youtube_url: str) -> Dict[str, Union[str, List[Dict]]]:
        """Extract transcript and metadata from YouTube video using hybrid approach
        
        Uses youtube-transcript-api for transcripts (primary) and yt-dlp for metadata.
        Falls back to yt-dlp transcript extraction if primary fails.
        
        Args:
            youtube_url: URL of the YouTube video
            
        Returns:
            Dictionary containing video metadata and transcript
        """
        # Initialize variables in outer scope
        transcript_text = None
        video_id = self._extract_video_id(youtube_url)
        
        try:
            # STEP 1: Try to get transcript via youtube-transcript-api (PRIMARY METHOD)
            transcript_text = self._get_transcript_via_api(video_id)
            
            # STEP 2: Get video metadata via yt-dlp (simplified for metadata only)
            # Configure yt-dlp options - simpler since we only need metadata now
            ydl_opts = {
                'skip_download': True,
                'writeinfojson': True,
                # Simplified settings focused on metadata extraction
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web'],  # Just web client for metadata
                    }
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                'sleep_interval': 0,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info
                info = ydl.extract_info(youtube_url, download=False)
                
                # Get basic metadata
                metadata = {
                    'title': info.get('title', ''),
                    'description': info.get('description', ''),
                    'uploader': info.get('uploader', ''),
                    'upload_date': info.get('upload_date', ''),
                    'duration': info.get('duration', 0),
                    'duration_string': info.get('duration_string', ''),
                    'view_count': info.get('view_count', 0),
                    'url': youtube_url,
                    'video_id': info.get('id', ''),
                    'channel_url': info.get('channel_url', ''),
                    'tags': info.get('tags', []),
                }
                
                # STEP 3: Handle transcript - use primary result or fallback to yt-dlp
                content_type = "transcript"  # Default assumption
                
                if transcript_text and len(transcript_text.strip()) > 100:
                    # SUCCESS: We have a good transcript from youtube-transcript-api
                    print(f"✅ Using YouTube Transcript API result: {len(transcript_text)} characters")
                else:
                    # FALLBACK: Try yt-dlp transcript extraction
                    print("🔄 Falling back to yt-dlp transcript extraction...")
                    yt_dlp_transcript = self._try_yt_dlp_transcript_extraction(info)
                    
                    if yt_dlp_transcript and len(yt_dlp_transcript.strip()) > 100:
                        transcript_text = yt_dlp_transcript
                        print(f"✅ yt-dlp transcript fallback successful: {len(transcript_text)} characters")
                    elif yt_dlp_transcript:
                        transcript_text = yt_dlp_transcript
                        print(f"⚠️  yt-dlp transcript fallback partial: {len(transcript_text)} characters")
                    else:
                        # LAST RESORT: Use description
                        description = info.get('description', '')
                        if description and len(description.strip()) > 50:
                            transcript_text = description
                            content_type = "description"
                            print(f"⚠️  No transcript available, using video description: {len(description)} characters")
                        else:
                            transcript_text = 'No transcript available'
                            content_type = "none"
                            print("⚠️  No content available - no transcript or usable description")
                
                return {
                    'metadata': metadata,
                    'transcript': transcript_text,
                    'content_type': content_type,
                    'success': True
                }
                
        except Exception as e:
            # If yt-dlp fails but we have a transcript from the API, create minimal metadata
            if transcript_text and len(transcript_text.strip()) > 100:
                # Silent fallback - we have transcript, metadata is optional
                video_id = self._extract_video_id(youtube_url)
                
                return {
                    'metadata': {
                        'title': f'Video {video_id}',  # Basic fallback title
                        'description': '',
                        'uploader': 'Unknown',
                        'upload_date': '',
                        'duration': 0,
                        'duration_string': '',
                        'view_count': 0,
                        'url': youtube_url,
                        'video_id': video_id,
                        'channel_url': '',
                        'tags': [],
                    },
                    'transcript': transcript_text,
                    'content_type': 'transcript',
                    'success': True
                }
            else:
                return {
                    'error': str(e),
                    'success': False
                }
    
    def _parse_srv3_transcript(self, srv3_data: str) -> str:
        """Parse SRV3 format transcript data"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(srv3_data)
            
            transcript_lines = []
            for text_elem in root.findall('.//text'):
                text_content = text_elem.text or ""
                if text_content.strip():
                    # Clean up the text
                    text_content = re.sub(r'&[a-zA-Z]+;', '', text_content)
                    text_content = text_content.strip()
                    if text_content:
                        transcript_lines.append(text_content)
            
            return ' '.join(transcript_lines)
        except Exception as e:
            print(f"Error parsing SRV3 transcript: {e}")
            return ""
    
    def _parse_generic_transcript(self, transcript_data: str) -> str:
        """Parse generic transcript formats (JSON3, VTT, TTML)"""
        try:
            transcript_lines = []
            
            # Try JSON format first
            if transcript_data.strip().startswith('{') or transcript_data.strip().startswith('['):
                import json
                try:
                    data = json.loads(transcript_data)
                    if isinstance(data, dict) and 'events' in data:
                        # YouTube JSON3 format
                        for event in data['events']:
                            if 'segs' in event:
                                for seg in event['segs']:
                                    if 'utf8' in seg:
                                        text = seg['utf8'].strip()
                                        if text and text not in ['♪', '[Music]', '[Applause]']:
                                            transcript_lines.append(text)
                    elif isinstance(data, list):
                        # Other JSON formats
                        for item in data:
                            if isinstance(item, dict) and 'text' in item:
                                text = item['text'].strip()
                                if text:
                                    transcript_lines.append(text)
                except json.JSONDecodeError:
                    pass
            
            # Try VTT format
            elif 'WEBVTT' in transcript_data or '-->' in transcript_data:
                lines = transcript_data.split('\n')
                for line in lines:
                    line = line.strip()
                    # Skip timestamps and empty lines
                    if (line and not line.startswith('WEBVTT') and 
                        '-->' not in line and not line.isdigit() and
                        not line.startswith('NOTE') and not line.startswith('STYLE')):
                        # Clean HTML tags if present
                        import re
                        clean_line = re.sub(r'<[^>]+>', '', line)
                        if clean_line.strip():
                            transcript_lines.append(clean_line.strip())
            
            # Try XML/TTML format
            elif '<' in transcript_data and '>' in transcript_data:
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(transcript_data)
                    # Find all text elements regardless of namespace
                    for elem in root.iter():
                        if elem.text and elem.text.strip():
                            text = elem.text.strip()
                            if text not in ['♪', '[Music]', '[Applause]']:
                                transcript_lines.append(text)
                except ET.ParseError:
                    pass
            
            result = ' '.join(transcript_lines)
            return result if result.strip() else ""
            
        except Exception as e:
            print(f"Error parsing generic transcript: {e}")
            return ""
    
    async def generate_summary(self, transcript: str, metadata: Dict, 
                             summary_type: str = "comprehensive") -> Dict[str, str]:
        """Generate AI summary of the video transcript
        
        Args:
            transcript: The video transcript text
            metadata: Video metadata dictionary
            summary_type: Type of summary ('comprehensive', 'audio', 'bullet-points', 'key-insights', 'executive', 'adaptive')
            
        Returns:
            Dictionary containing different summary formats
        """
        
        # Prepare context and prompts based on summary type
        base_context = f"""
        Video Title: {metadata.get('title', 'Unknown')}
        Channel: {metadata.get('uploader', 'Unknown')}
        Upload Date (YYYYMMDD): {metadata.get('upload_date', 'Unknown')}
        Duration (seconds): {metadata.get('duration', 0)}
        URL: {metadata.get('url', 'Unknown')}

        Transcript (truncated to 8000 chars):
        {transcript[:8000]}
        """
        
        prompts = {
            "comprehensive": f"""
            {base_context}

            Create an **executive report** that extracts key insights and strategic implications from this video content.

            **EXECUTIVE SUMMARY**
            Write 2–3 concise sentences capturing the video's main purpose, key findings, and strategic takeaway. Frame the final sentence as a "so what" for leadership decision-making. Keep it sharp and high-level — no more than 3 sentences.

            **KEY INSIGHTS & ANALYSIS**
            Organise the content into 2–4 natural sections with **short, descriptive headings** (2–5 words maximum). For each section:
            - Begin with 1–2 sentences establishing the theme and relevance (vary: "Focus", "Scope", "Context", etc.)
            - Present 3–5 key findings as **uniform, verb-led bullets** (e.g., "Verify version (0.88+) with claude –version", "Switch providers via base URL", "Enable cost tracking...")
            - Conclude with strategic implications woven naturally into prose (avoid labelling "Implications:")

            **STRATEGIC RECOMMENDATIONS**
            Provide 3–4 clear, actionable recommendations in **tiered bullets** (headline + supporting details):  
            - Top-level bullet = decisive headline (*Institutionalise cost governance*, *Adopt hybrid workflows*)  
                • Supporting bullets = 1–2 specific implementation details  

            **Writing Guidelines:**
            - Assume audience is senior leadership — write in crisp, consulting-style prose (think McKinsey/BCG)
            - Emphasise strategic implications over raw facts
            - Use professional language (British/Canadian spelling)
            - Include timestamps only when they add clarity
            - Vary section openings naturally (avoid mechanical repetition)
            - Create sections that emerge organically from content
            - Never speculate beyond presented material
            - Ensure natural flow — reports should feel executive-authored, not AI-generated
            """,

            "audio": f"""
            {base_context}

            You are writing a script for text-to-speech audio. Create a conversational, flowing summary that sounds natural when spoken aloud. Present the actual findings and insights directly - never describe what the video does or what the reviewer says.

            **Script Structure:**

            **Opening:** Start with 2-3 sentences that immediately introduce the main topic and key conclusion. No "this video covers" - jump straight into the substance.

            **Main Content:** Analyze the transcript to identify major topics, then present them using smooth conversational transitions between sections. Never use headings or bullet points. Instead, use natural verbal signposts like:
            - "First, let's look at the performance results..."
            - "Moving on to build quality..."
            - "When it comes to pricing..."
            - "The most important finding was..."
            - "However, there's an important trade-off..."

            **Conclusion:** End with "So what's the bottom line?" or "In the end..." followed by the main takeaway and practical recommendations. **Crucially, if the video is a review, ensure this final verdict explicitly mentions price, value, and the final cost-benefit analysis, as this is often the most important takeaway for the audience.**

            **Critical Writing Rules:**
            - Write in flowing paragraphs only - no lists, bullets, or visual formatting
            - **Keep paragraphs focused and concise:** To maintain listener engagement, ensure each paragraph covers a single main idea. If a topic is complex, break it into multiple shorter paragraphs rather than one long one
            - Use short, clear sentences that are easy to follow when spoken
            - Spell out acronyms the first time ("Artificial Intelligence, or A-I")
            - Include specific details, numbers, model names, and prices
            - Use natural pauses with commas and periods to guide TTS pacing
            - Cover all major topics - don't skip important sections like pricing, specifications, or final recommendations
            - Scale content to match complexity - comprehensive coverage for detailed content, concise for simple topics

            **Avoid Meta-Commentary:**
            Present findings directly and avoid phrases like "the video explains" or "the reviewer discusses." Only use attribution when it's essential to clarify that a statement is a subjective opinion or conclusion, not an objective fact.
            - GOOD (Direct Fact): "The vacuum has twenty-two thousand Pascals of suction."
            - GOOD (Attributed Opinion): "The reviewer concludes the mopping is a generation ahead of the competition."
            - BAD (Weak Phrasing): "The reviewer then goes on to talk about the suction power."

            Write as if you're explaining the findings to a friend over coffee - professional but conversational, comprehensive but natural to listen to.
            """,

            "bullet-points": f"""
            {base_context}

            Output ONLY this Markdown skeleton, filling in the brackets. Keep each bullet ≤ 18 words.

            • **Main topic:** [brief]
            • **Key points:**
              - [point 1]
              - [point 2]
              - [point 3]
            • **Takeaway:** [single sentence]
            • **Best for:** [audience]
            """,

            "key-insights": f"""
            {base_context}

            Extract actionable insights only. Provide numbered Markdown items, each ≤ 24 words, no fluff:
            1) **Core message:** [one sentence]
            2) **Top 3 insights:** [three sub‑bullets]
            3) **Actions/next steps:** [2–4 sub‑bullets]
            4) **Why watch:** [one sentence]

            Do not speculate; write **Unknown** if the transcript doesn't support a claim.
            """,
            
            "executive": f"""
            {base_context}

            Format this as a structured EXECUTIVE REPORT. Analyze the content and divide it into 2-4 logical parts based on the video's natural flow.

            **📊 EXECUTIVE SUMMARY**
            2-3 sentences that capture the video's main purpose, key findings, and business/practical value. Professional tone.

            **📋 PART 1: (Give this section a descriptive title)**
            
            **Overview:** 2-3 sentences explaining what this part covers and its relevance.
            
            **Key Points:**
            • Specific finding/point with details
            • Specific finding/point with details  
            • Specific finding/point with details
            
            **Conclusion:** 1-2 sentences summarizing the implications of this section.

            **📋 PART 2: (Give this section a descriptive title)**
            
            **Overview:** 2-3 sentences explaining what this part covers and its relevance.
            
            **Key Points:**
            • Specific finding/point with details
            • Specific finding/point with details
            • Specific finding/point with details
            
            **Conclusion:** 1-2 sentences summarizing the implications of this section.

            **📋 PART 3: (Give this section a descriptive title - if applicable)**
            
            **Overview:** 2-3 sentences explaining what this part covers and its relevance.
            
            **Key Points:**
            • Specific finding/point with details
            • Specific finding/point with details
            • Specific finding/point with details
            
            **Conclusion:** 1-2 sentences summarizing the implications of this section.

            **🎯 STRATEGIC RECOMMENDATIONS**
            • Actionable next step or key takeaway
            • Actionable next step or key takeaway
            • Actionable next step or key takeaway

            **Guidelines:**
            - Divide content into 2-4 logical parts (not artificial divisions)
            - Use professional, analytical language
            - Include timestamps where helpful
            - Focus on insights and implications, not just facts
            - Keep each section balanced and substantive
            - If content doesn't fit this structure well, adapt the format accordingly
            - British/Canadian spelling; no speculation
            """,
            
            "adaptive": f"""
            {base_context}

            You are an expert content analyst. Based on the transcript, silently choose the most effective summary format for this specific video and produce ONLY the summary.

            **Consider (internally, without writing it out):**
            - Content complexity and technical depth
            - Educational vs entertainment value
            - Tutorial/procedural vs discussion/opinion
            - Information density and duration
            - Likely audience sophistication implied by the transcript

            **Available formats (choose one, or design a simple custom layout if clearly better):**
            1) Comprehensive detailed analysis
            2) Executive brief
            3) Key insights extraction
            4) Step-by-step breakdown (for tutorials/procedures)
            5) Custom adaptive format (only if it's clearly superior)

            **Output rules (must follow):**
            - Do NOT explain your choice or approach; no meta-commentary
            - Start directly with the summary content (no prefaces)
            - Use clear, scannable structure (short headings and/or bullets as appropriate)
            - British/Canadian spelling; neutral, precise tone by default
            - Include [mm:ss] timestamps ONLY if they are explicitly present or derivable from the transcript; otherwise omit them
            - No speculation or external facts; if a needed detail is missing, write **Unknown**
            - Avoid filler signposting ("In this section…", "We will discuss…"); write the content itself
            - If the transcript is sparse/inaudible/mostly music, summarise the **available** information and state **Unknown** for specifics
            - End with a single concise takeaway sentence beginning **Bottom line:** unless the chosen format already has a clear conclusion

            **Length guidance (not a hard limit):**
            - Short videos / light content: 120–180 words
            - Dense or technical content: 250–500 words
            - Tutorials: use a step-wise structure with concise steps (≤ 12 words per step)
            """,
        }
        
        try:
            # Generate the summary
            response = await self.llm.ainvoke([
                HumanMessage(content=prompts.get(summary_type, prompts["comprehensive"]))
            ])
            
            summary_text = response.content
            
            # Also generate a quick title/headline
            title_prompt = f"""
            Write a single, specific headline (12–16 words, no emojis) that states subject and concrete value.
            Source title: {metadata.get('title', '')}
            Transcript excerpt:
            {transcript[:1200]}
            """
            
            title_response = await self.llm.ainvoke([
                HumanMessage(content=title_prompt)
            ])
            
            return {
                'summary': summary_text,
                'headline': title_response.content,
                'summary_type': summary_type,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Summary generation error: {str(e)}")
            return {
                'error': f"Failed to generate summary: {str(e)}",
                'summary': "Summary generation failed",
                'headline': "Error generating headline"
            }
    
    async def analyze_content(self, transcript: str, metadata: Dict) -> Dict[str, Union[str, List[str]]]:
        """Perform content analysis including topic categorization and sentiment"""
        
        analysis_prompt = f"""
        Analyze this YouTube video content and provide:
        
        Video: {metadata.get('title', 'Unknown')}
        Transcript: {transcript[:4000]}
        
        Please provide:
        1. Content Category (choose 1-2): Education, Entertainment, Technology, Business, Health, DIY, News, Gaming, Lifestyle, Science, etc.
        2. Sentiment (Overall tone): Positive, Negative, Neutral, Mixed
        3. Target Audience: Who would benefit most from this content?
        4. Complexity Level: Beginner, Intermediate, Advanced
        5. Key Topics (3-5 tags): Main subjects discussed
        6. Content Type: Tutorial, Review, Discussion, News, Documentary, etc.
        
        Format as JSON:
        {{
            "category": ["Primary Category", "Secondary Category"],
            "sentiment": "sentiment",
            "target_audience": "description",
            "complexity_level": "level",
            "key_topics": ["topic1", "topic2", "topic3"],
            "content_type": "type",
            "educational_value": "High/Medium/Low",
            "entertainment_value": "High/Medium/Low"
        }}
        """
        
        try:
            response = await self.llm.ainvoke([
                HumanMessage(content=analysis_prompt)
            ])
            
            # Try to parse JSON response
            import json
            try:
                analysis = json.loads(response.content.strip())
            except:
                # Fallback if JSON parsing fails
                analysis = {
                    "category": ["General"],
                    "sentiment": "Neutral",
                    "target_audience": "General audience",
                    "complexity_level": "Intermediate",
                    "key_topics": ["General content"],
                    "content_type": "Discussion",
                    "educational_value": "Medium",
                    "entertainment_value": "Medium"
                }
            
            return analysis
            
        except Exception as e:
            print(f"Content analysis error: {str(e)}")
            return {
                "error": f"Analysis failed: {str(e)}",
                "category": ["Unknown"],
                "sentiment": "Unknown"
            }
    
    async def process_video(self, youtube_url: str, summary_type: str = "comprehensive") -> Dict:
        """Complete processing pipeline for a YouTube video
        
        Args:
            youtube_url: YouTube video URL
            summary_type: Type of summary to generate
            
        Returns:
            Complete analysis dictionary
        """
        print(f"Processing video: {youtube_url}")
        
        # Step 1: Extract transcript
        print("Extracting transcript...")
        transcript_data = self.extract_transcript(youtube_url)
        
        if not transcript_data.get('success'):
            return {
                'error': transcript_data.get('error'),
                'url': youtube_url,
                'processed_at': datetime.now().isoformat()
            }
        
        metadata = transcript_data['metadata']
        transcript = transcript_data['transcript']
        content_type = transcript_data.get('content_type', 'transcript')
        
        # REJECT only videos with truly no content (very rare now with hybrid system)
        if content_type == 'none' or len(transcript.strip()) < 50:
            print("🚫 REJECTED: Cannot generate summary - no usable content available")
            return {
                'error': 'No usable content available for this video. Neither transcript nor description could be extracted. This may be a private video, age-restricted content, or have other access restrictions.',
                'url': youtube_url,
                'metadata': metadata,
                'transcript_available': False,
                'processed_at': datetime.now().isoformat(),
                'suggestion': "Try a different video or check if this video is publicly accessible."
            }
        elif content_type == 'description':
            # Allow description-only but warn the user
            print("⚠️  WARNING: Only video description available - summary will be limited")
            # Continue processing but mark as limited accuracy
        
        if len(transcript.strip()) < 50:
            print(f"⚠️  Transcript extracted: {len(transcript)} characters (insufficient for processing)")
        else:
            print(f"✅ Transcript extracted: {len(transcript)} characters")
        
        # Check if transcript is too short to be useful
        if len(transcript.strip()) < 50:  # Less than 50 characters is likely unusable
            video_title = metadata.get('title', 'Unknown video')
            return {
                'error': f"❌ No usable transcript found for '{video_title}'. This video appears to have no captions or subtitles available. Please try a different video that includes captions/subtitles for best results.",
                'url': youtube_url,
                'metadata': metadata,
                'transcript_length': len(transcript),
                'processed_at': datetime.now().isoformat(),
                'suggestion': "Look for videos with the [CC] closed captions icon on YouTube, or videos from channels that typically include subtitles."
            }
        
        # Step 2: Generate summary
        print("Generating summary...")
        summary_data = await self.generate_summary(transcript, metadata, summary_type)
        
        # Step 3: Analyze content
        print("Analyzing content...")
        analysis_data = await self.analyze_content(transcript, metadata)
        
        # Combine all results
        result = {
            'url': youtube_url,
            'metadata': metadata,
            'transcript': transcript,
            'summary': summary_data,
            'analysis': analysis_data,
            'processed_at': datetime.now().isoformat(),
            'processor_info': {
                'llm_provider': self.llm_provider,
                'model': getattr(self.llm, 'model_name', getattr(self.llm, 'model', self.model))
            }
        }
        
        print("Processing complete!")
        return result

    def generate_tts_audio(self, text: str, output_filename: str = None) -> Optional[str]:
        """Generate TTS audio using OpenAI API
        
        Args:
            text: Text to convert to speech
            output_filename: Optional filename (will generate if not provided)
            
        Returns:
            Path to generated audio file or None if failed
        """
        try:
            # Get API key from environment (reuse existing OpenAI key)
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                print("❌ OPENAI_API_KEY not found in environment")
                return None
            
            # Generate filename if not provided
            if not output_filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"audio_summary_{timestamp}.mp3"
            
            # Ensure exports directory exists
            exports_dir = Path('exports')
            exports_dir.mkdir(exist_ok=True)
            output_path = exports_dir / output_filename
            
            # Prepare OpenAI TTS API request
            url = "https://api.openai.com/v1/audio/speech"
            payload = {
                "model": "tts-1",  # Standard quality (tts-1-hd for higher quality)
                "input": text,
                "voice": "fable"  # CURRENT: Warm, engaging male voice - great for storytelling
            }
            
            # OpenAI TTS Voice Options (change "voice" above to switch):
            # "alloy"   - Male (neutral): Natural, smooth young male voice, could pass as gender-neutral
            # "echo"    - Male: Articulate, precise young male voice, very proper English style
            # "fable"   - Male: Warm, engaging young male voice, perfect for storytelling (CURRENT)
            # "onyx"    - Male: Deep, authoritative older male voice, BBC presenter style  
            # "nova"    - Female: Bright, energetic young female voice
            # "shimmer" - Female: Soft, gentle young female voice, soothing tone
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            print("🎙️ Generating TTS audio with OpenAI...")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                print(f"✅ TTS audio saved to {output_path}")
                return str(output_path)
            else:
                print(f"❌ OpenAI TTS API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ TTS generation failed: {str(e)}")
            return None

        # HUME AI TTS (COMMENTED OUT - keeping for reference)
        # try:
        #     # Get API key from environment
        #     api_key = os.getenv('HUME_API_KEY')
        #     if not api_key:
        #         print("❌ HUME_API_KEY not found in environment")
        #         return None
        #     
        #     # Prepare API request
        #     url = "https://api.hume.ai/v0/tts/file"
        #     payload = {
        #         "utterances": [{
        #             "text": text
        #         }],
        #         "format": {"type": "mp3"}
        #     }
        #     headers = {
        #         "X-Hume-Api-Key": api_key,
        #         "Content-Type": "application/json"
        #     }
        #     
        #     print("🎙️ Generating TTS audio...")
        #     response = requests.post(url, headers=headers, json=payload, timeout=30)
        #     
        #     if response.status_code == 200:
        #         with open(output_path, "wb") as f:
        #             f.write(response.content)
        #         print(f"✅ TTS audio saved to {output_path}")
        #         return str(output_path)
        #     else:
        #         print(f"❌ TTS API Error: {response.status_code} - {response.text}")
        #         return None
        #         
        # except Exception as e:
        #     print(f"❌ TTS generation failed: {str(e)}")
        #     return None


async def main():
    """Example usage of the YouTube Summarizer"""
    
    # Initialize summarizer (requires API keys in .env file)
    try:
        summarizer = YouTubeSummarizer(llm_provider="openai", model="gpt-4")
    except Exception as e:
        print(f"Failed to initialize summarizer: {e}")
        print("Make sure you have OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file")
        return
    
    # Example YouTube URL (replace with actual video)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll as safe test
    
    # Process the video
    result = await summarizer.process_video(test_url, summary_type="comprehensive")
    
    # Display results
    if 'error' in result:
        print(f"Error: {result['error']}")
    else:
        print("\n" + "="*60)
        print("YOUTUBE VIDEO SUMMARY")
        print("="*60)
        print(f"Title: {result['metadata']['title']}")
        print(f"Channel: {result['metadata']['uploader']}")
        print(f"Duration: {result['metadata']['duration']} seconds")
        print(f"Views: {result['metadata']['view_count']:,}")
        
        print(f"\nHeadline: {result['summary']['headline']}")
        print(f"\nSummary:\n{result['summary']['summary']}")
        
        print(f"\nContent Analysis:")
        analysis = result['analysis']
        print(f"Category: {', '.join(analysis.get('category', ['Unknown']))}")
        print(f"Sentiment: {analysis.get('sentiment', 'Unknown')}")
        print(f"Target Audience: {analysis.get('target_audience', 'Unknown')}")
        print(f"Complexity: {analysis.get('complexity_level', 'Unknown')}")
        print(f"Key Topics: {', '.join(analysis.get('key_topics', ['Unknown']))}")


if __name__ == "__main__":
    asyncio.run(main())