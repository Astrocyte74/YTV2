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
                
                # Fallback: use description if no transcript available
                if not transcript_text:
                    transcript_text = info.get('description', 'No transcript available')
                    print("⚠️  No captions/transcript found, using video description as fallback")
                elif len(transcript_text.strip()) < 50:  # Very short transcript, probably failed
                    description = info.get('description', '')
                    if len(description) > len(transcript_text):
                        transcript_text = description
                        print("⚠️  Transcript too short, using video description instead")
                
                return {
                    'metadata': metadata,
                    'transcript': transcript_text,
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
            summary_type: Type of summary ('comprehensive', 'brief', 'bullet-points', 'key-insights', 'executive', 'adaptive')
            
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

            Format this as a structured **EXECUTIVE REPORT**.  
            Your goal: extract insights, not just recount content.  
            Divide the video into 2–4 logical parts that reflect its **natural flow**. If the content does not lend itself to this structure, adapt gracefully while keeping clarity and professionalism.  

            **EXECUTIVE SUMMARY**  
            2–3 sentences capturing the video's main purpose, core findings, and practical/business value. Use a professional, concise tone.  

            **PART 1: (Insert a descriptive title)**  
            **Overview:** 2–3 sentences explaining what this section covers and why it matters.  
            **Key Points:**  
            • Clear, specific point with details  
            • Clear, specific point with details  
            • Clear, specific point with details  
            **Conclusion:** 1–2 sentences on the implications of this section.  

            **PART 2: (Insert a descriptive title)**  
            (Follow the same structure as Part 1.)  

            **PART 3 (optional): (Insert a descriptive title)**  
            (Follow the same structure as Part 1, only if the video warrants it.)  

            **STRATEGIC RECOMMENDATIONS**  
            • Actionable next step or distilled takeaway  
            • Actionable next step or distilled takeaway  
            • Actionable next step or distilled takeaway  

            **Guidelines for Output:**  
            - Prioritise **insights and implications** over raw facts  
            - Use **professional, analytical language** (British/Canadian spelling)  
            - Insert **timestamps where they add clarity**  
            - Keep each section balanced and substantive  
            - Never invent or speculate beyond the video's content  
            - If the content resists this structure, **adapt it logically** while retaining summary + sections + recommendations
            """,

            "brief": f"""
            {base_context}

            Write a 120–180 word MARKDOWN brief as a single compact paragraph (no emojis, no headings, no bullets). Structure it as:
            - Opening thesis: one sentence stating what the video does and why it matters.
            - Key specifics: 3–5 sentences with concrete details, models, figures, or steps; add [mm:ss] timestamps if inferable.
            - Significance: 1–2 sentences on implications or practical value.
            - Caveats: one sentence noting limitations, uncertainties, or safety notes explicitly mentioned.
            - Bottom line: one sentence starting with **Bottom line:** that crystallises the takeaway.

            Rules:
            - Neutral tone; British/Canadian spelling.
            - Do not speculate; if the transcript does not support a claim, write **Unknown**.
            - Prefer short, direct sentences; avoid hype and filler.
            - Include proper nouns exactly as given (e.g., model numbers, dates).
            - Do not mention a target audience.
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
            
            You are an expert content analyst. Based on the video transcript, choose the most effective summary approach for this specific content. Consider:
            
            **Analysis factors:**
            - Content complexity and technical depth
            - Educational vs entertainment value
            - Tutorial/instructional vs discussion/opinion
            - Video length and information density
            - Target audience sophistication level
            
            **Your choices:**
            1. **Comprehensive detailed analysis** - For complex technical content, tutorials, or educational material that benefits from structured breakdown
            2. **Executive brief format** - For business content, news, or straightforward informational videos 
            3. **Key insights extraction** - For thought leadership, interviews, or concept-heavy discussions
            4. **Step-by-step breakdown** - For how-to content, procedures, or instructional material
            5. **Custom adaptive format** - Design your own structure that best serves this specific content
            
            **Instructions:**
            - First, analyze the content and decide which approach will be most valuable
            - Then create the summary using your chosen format
            - Be flexible with length - use as much or as little space as needed
            - Include timestamps when helpful
            - Focus on maximum value for the viewer
            - Use clear, engaging formatting with appropriate headings and structure
            - If you create a custom format, make it intuitive and scannable
            
            Start with a brief note like "**Approach chosen:** [your choice and why]" then provide the summary.
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
        
        print(f"Transcript extracted: {len(transcript)} characters")
        
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