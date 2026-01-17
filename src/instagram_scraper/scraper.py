"""Core Instagram saved posts scraper using Instaloader."""

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import instaloader
from instaloader import Post, Profile


@dataclass
class SavedPost:
    """Represents a saved Instagram post."""

    shortcode: str
    post_url: str
    owner_username: str
    owner_full_name: str
    caption: str
    timestamp: str
    likes: int
    is_video: bool
    image_urls: list[str]
    video_url: Optional[str]
    local_image_paths: list[str]
    local_video_path: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class InstagramSavedPostsScraper:
    """Scraper for Instagram saved posts."""

    def __init__(
        self,
        username: str,
        output_dir: str = "output",
        session_file: Optional[str] = None,
    ):
        """
        Initialize the scraper.

        Args:
            username: Your Instagram username
            output_dir: Directory to save downloaded content
            session_file: Path to saved session file (optional)
        """
        self.username = username
        self.output_dir = Path(output_dir)
        self.session_file = session_file
        self.loader = self._create_loader()
        self._logged_in = False

    def _create_loader(self) -> instaloader.Instaloader:
        """Create and configure the Instaloader instance."""
        loader = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=True,
            compress_json=False,
            post_metadata_txt_pattern="",
            max_connection_attempts=3,
        )
        return loader

    def login(self, password: Optional[str] = None) -> bool:
        """
        Login to Instagram.

        Args:
            password: Instagram password (if not using saved session)

        Returns:
            True if login successful
        """
        try:
            # Try to load existing session first
            if self.session_file and os.path.exists(self.session_file):
                self.loader.load_session_from_file(self.username, self.session_file)
                self._logged_in = True
                return True

            # Try default session location
            try:
                self.loader.load_session_from_file(self.username)
                self._logged_in = True
                return True
            except FileNotFoundError:
                pass

            # Login with password
            if password:
                self.loader.login(self.username, password)
                # Save session for future use
                session_path = self.session_file or f"session-{self.username}"
                self.loader.save_session_to_file(session_path)
                self._logged_in = True
                return True

            return False

        except instaloader.exceptions.BadCredentialsException:
            raise ValueError("Invalid username or password")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            raise ValueError(
                "Two-factor authentication required. Please use the interactive login."
            )
        except Exception as e:
            raise RuntimeError(f"Login failed: {e}")

    def interactive_login(self) -> bool:
        """
        Perform interactive login (handles 2FA).

        Returns:
            True if login successful
        """
        try:
            self.loader.interactive_login(self.username)
            session_path = self.session_file or f"session-{self.username}"
            self.loader.save_session_to_file(session_path)
            self._logged_in = True
            return True
        except Exception as e:
            raise RuntimeError(f"Interactive login failed: {e}")

    def _ensure_logged_in(self):
        """Ensure the user is logged in."""
        if not self._logged_in:
            raise RuntimeError("Not logged in. Call login() first.")

    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """Sanitize text for use in filenames."""
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*\n\r]', '_', text)
        # Limit length
        return sanitized[:max_length].strip()

    def _extract_post_data(self, post: Post, download_media: bool = True) -> SavedPost:
        """
        Extract data from an Instagram post.

        Args:
            post: Instaloader Post object
            download_media: Whether to download images/videos

        Returns:
            SavedPost object with extracted data
        """
        # Get caption (post text)
        caption = post.caption or ""

        # Get owner info
        owner_username = post.owner_username
        try:
            owner_full_name = post.owner_profile.full_name
        except Exception:
            owner_full_name = owner_username

        # Get image URLs
        image_urls = []
        if post.typename == "GraphSidecar":
            # Carousel post - multiple images
            for node in post.get_sidecar_nodes():
                if not node.is_video:
                    image_urls.append(node.display_url)
        elif not post.is_video:
            image_urls.append(post.url)

        # Get video URL if applicable
        video_url = post.video_url if post.is_video else None

        # Create post directory
        post_dir = self.output_dir / owner_username / post.shortcode
        post_dir.mkdir(parents=True, exist_ok=True)

        local_image_paths = []
        local_video_path = None

        if download_media:
            # Download images
            for idx, img_url in enumerate(image_urls):
                img_path = post_dir / f"image_{idx + 1}.jpg"
                if not img_path.exists():
                    try:
                        self.loader.context.get_and_write_raw(img_url, img_path)
                        local_image_paths.append(str(img_path))
                    except Exception as e:
                        print(f"Warning: Failed to download image: {e}")
                else:
                    local_image_paths.append(str(img_path))

            # Download video if present
            if video_url:
                video_path = post_dir / "video.mp4"
                if not video_path.exists():
                    try:
                        self.loader.context.get_and_write_raw(video_url, video_path)
                        local_video_path = str(video_path)
                    except Exception as e:
                        print(f"Warning: Failed to download video: {e}")
                else:
                    local_video_path = str(video_path)

            # Also download thumbnail for videos
            if post.is_video and post.url:
                thumb_path = post_dir / "thumbnail.jpg"
                if not thumb_path.exists():
                    try:
                        self.loader.context.get_and_write_raw(post.url, thumb_path)
                        local_image_paths.append(str(thumb_path))
                    except Exception:
                        pass

        return SavedPost(
            shortcode=post.shortcode,
            post_url=f"https://www.instagram.com/p/{post.shortcode}/",
            owner_username=owner_username,
            owner_full_name=owner_full_name,
            caption=caption,
            timestamp=post.date_utc.isoformat(),
            likes=post.likes,
            is_video=post.is_video,
            image_urls=image_urls,
            video_url=video_url,
            local_image_paths=local_image_paths,
            local_video_path=local_video_path,
        )

    def get_saved_posts(
        self,
        max_posts: Optional[int] = None,
        download_media: bool = True,
        delay_between_posts: float = 2.0,
    ) -> Iterator[SavedPost]:
        """
        Fetch saved posts from Instagram.

        Args:
            max_posts: Maximum number of posts to fetch (None for all)
            download_media: Whether to download images/videos
            delay_between_posts: Delay between fetching posts (to avoid rate limits)

        Yields:
            SavedPost objects
        """
        self._ensure_logged_in()

        try:
            profile = Profile.from_username(self.loader.context, self.username)
        except Exception as e:
            raise RuntimeError(f"Failed to get profile: {e}")

        count = 0

        try:
            for post in profile.get_saved_posts():
                if max_posts and count >= max_posts:
                    break

                try:
                    saved_post = self._extract_post_data(post, download_media)
                    yield saved_post
                    count += 1

                    # Delay to avoid rate limiting
                    if delay_between_posts > 0:
                        time.sleep(delay_between_posts)

                except Exception as e:
                    print(f"Warning: Failed to process post {post.shortcode}: {e}")
                    continue

        except instaloader.exceptions.LoginRequiredException:
            raise RuntimeError("Login required to access saved posts")
        except instaloader.exceptions.PrivateProfileNotFollowedException:
            raise RuntimeError("Cannot access saved posts - profile issue")

    def scrape_and_save(
        self,
        max_posts: Optional[int] = None,
        download_media: bool = True,
        delay_between_posts: float = 2.0,
    ) -> list[SavedPost]:
        """
        Scrape saved posts and save to JSON.

        Args:
            max_posts: Maximum number of posts to fetch
            download_media: Whether to download images/videos
            delay_between_posts: Delay between posts

        Returns:
            List of SavedPost objects
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        posts = []

        for post in self.get_saved_posts(
            max_posts=max_posts,
            download_media=download_media,
            delay_between_posts=delay_between_posts,
        ):
            posts.append(post)

            # Save progress incrementally
            self._save_posts_json(posts)

        return posts

    def _save_posts_json(self, posts: list[SavedPost]):
        """Save posts to JSON file."""
        json_path = self.output_dir / "saved_posts.json"

        data = {
            "scraped_at": datetime.now().isoformat(),
            "username": self.username,
            "total_posts": len(posts),
            "posts": [p.to_dict() for p in posts],
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def export_captions_only(self, posts: list[SavedPost]) -> str:
        """
        Export just the captions to a text file.

        Args:
            posts: List of SavedPost objects

        Returns:
            Path to the exported file
        """
        txt_path = self.output_dir / "captions.txt"

        with open(txt_path, "w", encoding="utf-8") as f:
            for post in posts:
                f.write(f"=" * 60 + "\n")
                f.write(f"Post by @{post.owner_username}\n")
                f.write(f"URL: {post.post_url}\n")
                f.write(f"Date: {post.timestamp}\n")
                f.write(f"-" * 60 + "\n")
                f.write(f"{post.caption}\n\n")

        return str(txt_path)
