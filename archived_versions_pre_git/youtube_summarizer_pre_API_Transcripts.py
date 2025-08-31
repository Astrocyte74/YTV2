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
    
    def extract_transcript(self, youtube_url: str) -> Dict[str, Union[str, List[Dict]]]:
        """Extract transcript and metadata from YouTube video using yt-dlp
        
        Args:
            youtube_url: URL of the YouTube video
            
        Returns:
            Dictionary containing video metadata and transcript
        """
        try:
            # Configure yt-dlp options with enhanced bot avoidance
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US'],
                'skip_download': True,
                'outtmpl': str(self.downloads_dir / '%(title)s.%(ext)s'),
                'writeinfojson': True,
                # Enhanced bot avoidance options
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android_music', 'android', 'web'],
                        'player_skip': ['webpage'],
                        'skip': ['dash', 'hls'],
                    }
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                },
                # Additional anti-detection measures
                'sleep_interval': 2,
                'max_sleep_interval': 5,
                'sleep_interval_subtitles': 1,
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
                
                # Try to get transcript/subtitles
                transcript_text = ""
                
                # Check for automatic captions first
                if 'automatic_captions' in info and 'en' in info['automatic_captions']:
                    auto_caps = info['automatic_captions']['en']
                    for cap in auto_caps:
                        # Try different caption formats (srv3, json3, etc.)
                        if cap.get('ext') in ['srv3', 'json3', 'ttml', 'vtt']:
                            transcript_url = cap['url']
                            try:
                                import urllib.request
                                with urllib.request.urlopen(transcript_url) as response:
                                    transcript_data = response.read().decode('utf-8')
                                    if cap.get('ext') == 'srv3':
                                        transcript_text = self._parse_srv3_transcript(transcript_data)
                                    else:
                                        # For other formats, try to extract text content
                                        transcript_text = self._parse_generic_transcript(transcript_data)
                                    
                                    if transcript_text.strip():
                                        print(f"✅ Found automatic captions ({cap.get('ext')} format)")
                                        break
                            except Exception as e:
                                print(f"Error downloading automatic captions: {e}")
                
                # If no automatic captions, try manual subtitles
                if not transcript_text and 'subtitles' in info and 'en' in info['subtitles']:
                    manual_subs = info['subtitles']['en']
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
                                        print(f"✅ Found manual subtitles ({sub.get('ext')} format)")
                                        break
                            except Exception as e:
                                print(f"Error downloading manual subtitles: {e}")
                
                # Determine content type and handle fallback
                content_type = "transcript"  # Default assumption
                if not transcript_text:
                    description = info.get('description', '')
                    if description and len(description.strip()) > 50:
                        transcript_text = description
                        content_type = "description"
                        print(f"⚠️  No captions/transcript found, only video description available ({len(description)} chars)")
                    else:
                        transcript_text = 'No transcript available'
                        content_type = "none"
                        print("⚠️  No captions/transcript found and no usable video description - no content available")
                elif len(transcript_text.strip()) < 50:  # Very short transcript, probably failed
                    description = info.get('description', '')
                    if len(description) > len(transcript_text):
                        transcript_text = description
                        content_type = "description"
                        print(f"⚠️  Transcript too short ({len(transcript_text)} chars), only video description available ({len(description)} chars)")
                    else:
                        print(f"⚠️  Transcript too short ({len(transcript_text)} chars) and no better description available")
                
                return {
                    'metadata': metadata,
                    'transcript': transcript_text,
                    'content_type': content_type,
                    'success': True
                }
                
        except Exception as e:
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

            Create an audio-optimized summary designed for text-to-speech playback. Focus on the actual findings, insights, and conclusions rather than describing what the speaker does.

            **CRITICAL: Never describe the video or review process. Instead, present the actual content directly.**

            **Content Focus (as continuous speech, 180-250 words):**
            
            - **Open directly with the core finding or topic** - avoid "This video covers..." and jump straight to the substance
            - **Lead with the main finding or conclusion** - what did they discover or conclude?
            - **Include specific facts, numbers, and results** - not "they analyzed X" but "X performs like..."
            - **Focus on insights and outcomes** - avoid meta-descriptions like "the reviewer explains" or "they examine"
            - **Present concrete findings** - actual performance, measurements, comparisons, pros/cons
            - **Use natural speech transitions** but focus on substance: "The main finding is...", "Key results show...", "Performance-wise..."
            - **End with practical implications** - what should listeners actually know or do?

            **Avoid these patterns:**
            - "This video covers..." → Instead: directly state the topic/findings
            - "The reviewer discusses..." → Instead: state what was discussed
            - "They examine the..." → Instead: state what was found about it  
            - "The video covers..." → Instead: state the actual findings
            - "Then they analyze..." → Instead: state the analysis results
            - "It explains what makes..." → Instead: state what actually makes it work
            - "The video frames..." → Instead: present the actual context or significance

            **Write as one flowing narrative** focused on substantive content, findings, and actionable insights rather than describing the review process.
            
            **Audio-specific guidelines:**
            - Write for the ear, not the eye — use natural speech patterns
            - Use short, clear sentences (max 20 words each)
            - Include natural transitions ("However," "Moreover," "In summary")
            - Avoid abbreviations, acronyms without explanation, or complex punctuation
            - Use "and" instead of "&", spell out numbers under ten
            - Make it conversational but professional — like a knowledgeable colleague explaining over coffee
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
        
        # REJECT videos that only have descriptions, not real transcripts
        if content_type in ['description', 'none']:
            print("🚫 REJECTED: Cannot generate summary - no transcript available")
            return {
                'error': 'No transcript available for this video. This video only has a description/table of contents, which cannot provide accurate summaries. Please try a video with closed captions [CC] or manual subtitles.',
                'url': youtube_url,
                'metadata': metadata,
                'transcript_available': False,
                'processed_at': datetime.now().isoformat(),
                'suggestion': "Look for videos with the [CC] closed captions icon on YouTube, or videos from channels that typically include subtitles."
            }
        
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