"""Command-line interface for Instagram Saved Posts Scraper."""

import os
import sys
from getpass import getpass
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from .scraper import InstagramSavedPostsScraper, SavedPost

# Load environment variables
load_dotenv()

console = Console()


def print_banner():
    """Print the application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║         Instagram Saved Posts Scraper                     ║
║         Extract your saved posts with images & captions   ║
╚═══════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def print_post_summary(post: SavedPost, index: int):
    """Print a summary of a scraped post."""
    caption_preview = post.caption[:100] + "..." if len(post.caption) > 100 else post.caption
    caption_preview = caption_preview.replace("\n", " ")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Post #", str(index))
    table.add_row("From", f"@{post.owner_username}")
    table.add_row("URL", post.post_url)
    table.add_row("Date", post.timestamp[:10])
    table.add_row("Type", "Video" if post.is_video else "Image")
    table.add_row("Likes", str(post.likes))
    table.add_row("Caption", caption_preview or "(no caption)")
    table.add_row("Images", str(len(post.local_image_paths)))

    console.print(table)
    console.print()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Instagram Saved Posts Scraper - Extract your saved posts with images and captions."""
    pass


@cli.command()
@click.option(
    "--username", "-u",
    envvar="INSTAGRAM_USERNAME",
    help="Your Instagram username",
    prompt="Instagram username",
)
@click.option(
    "--password", "-p",
    envvar="INSTAGRAM_PASSWORD",
    help="Your Instagram password (or use interactive login)",
    default=None,
)
@click.option(
    "--output", "-o",
    default="output",
    help="Output directory for downloaded content",
    type=click.Path(),
)
@click.option(
    "--max-posts", "-n",
    default=None,
    type=int,
    help="Maximum number of posts to scrape (default: all)",
)
@click.option(
    "--no-media",
    is_flag=True,
    help="Skip downloading images and videos",
)
@click.option(
    "--delay",
    default=2.0,
    type=float,
    help="Delay between posts in seconds (default: 2.0)",
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    help="Use interactive login (required for 2FA)",
)
@click.option(
    "--session-file", "-s",
    default=None,
    help="Path to session file for login persistence",
)
def scrape(
    username: str,
    password: str,
    output: str,
    max_posts: int,
    no_media: bool,
    delay: float,
    interactive: bool,
    session_file: str,
):
    """
    Scrape your Instagram saved posts.

    Downloads all saved posts including images and captions.
    Results are saved to the output directory as JSON and individual media files.

    Example:
        instagram-scraper scrape -u myusername -i
    """
    print_banner()

    # Create scraper instance
    scraper = InstagramSavedPostsScraper(
        username=username,
        output_dir=output,
        session_file=session_file,
    )

    # Login
    console.print("\n[bold]Step 1: Authentication[/bold]")

    try:
        if interactive:
            console.print("Starting interactive login (may prompt for 2FA)...")
            scraper.interactive_login()
        else:
            # Try session first
            if scraper.login():
                console.print("[green]Logged in using saved session.[/green]")
            else:
                # Need password
                if not password:
                    password = getpass("Instagram password: ")
                scraper.login(password)
                console.print("[green]Login successful![/green]")

    except ValueError as e:
        console.print(f"[red]Login error: {e}[/red]")
        if "Two-factor" in str(e):
            console.print("[yellow]Tip: Use --interactive flag for 2FA login[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to login: {e}[/red]")
        sys.exit(1)

    # Scrape posts
    console.print("\n[bold]Step 2: Scraping Saved Posts[/bold]")

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    posts = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:

        if max_posts:
            task = progress.add_task("Scraping posts...", total=max_posts)
        else:
            task = progress.add_task("Scraping posts...", total=None)

        try:
            for post in scraper.get_saved_posts(
                max_posts=max_posts,
                download_media=not no_media,
                delay_between_posts=delay,
            ):
                posts.append(post)
                progress.update(task, advance=1, description=f"Scraped {len(posts)} posts...")

                # Save incrementally
                scraper._save_posts_json(posts)

        except KeyboardInterrupt:
            console.print("\n[yellow]Scraping interrupted by user.[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Error during scraping: {e}[/red]")

    # Results
    console.print(f"\n[bold]Step 3: Results[/bold]")

    if not posts:
        console.print("[yellow]No saved posts found.[/yellow]")
        return

    # Export captions
    captions_path = scraper.export_captions_only(posts)

    # Summary
    console.print(f"\n[green]Successfully scraped {len(posts)} saved posts![/green]\n")

    results_table = Table(title="Output Files", show_header=True)
    results_table.add_column("File", style="cyan")
    results_table.add_column("Description")

    results_table.add_row(
        str(output_path / "saved_posts.json"),
        "Full data with all metadata"
    )
    results_table.add_row(
        captions_path,
        "Captions/text only"
    )
    results_table.add_row(
        str(output_path / "<username>/<shortcode>/"),
        "Individual post media files"
    )

    console.print(results_table)

    # Show sample posts
    console.print("\n[bold]Sample of scraped posts:[/bold]\n")
    for i, post in enumerate(posts[:3], 1):
        print_post_summary(post, i)

    if len(posts) > 3:
        console.print(f"... and {len(posts) - 3} more posts")


@cli.command()
@click.option(
    "--username", "-u",
    envvar="INSTAGRAM_USERNAME",
    help="Your Instagram username",
    prompt="Instagram username",
)
@click.option(
    "--session-file", "-s",
    default=None,
    help="Path to session file",
)
def login(username: str, session_file: str):
    """
    Login to Instagram and save session.

    Use this to create a saved session that can be reused for future scrapes.
    Supports two-factor authentication.
    """
    print_banner()

    scraper = InstagramSavedPostsScraper(
        username=username,
        session_file=session_file,
    )

    console.print("\n[bold]Interactive Login[/bold]")
    console.print("This will prompt for your password and 2FA code if enabled.\n")

    try:
        scraper.interactive_login()
        console.print("\n[green]Login successful! Session saved.[/green]")
        console.print("You can now run 'scrape' without entering your password.")
    except Exception as e:
        console.print(f"\n[red]Login failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
@click.option(
    "--limit", "-n",
    default=10,
    type=int,
    help="Number of posts to show (default: 10)",
)
def view(json_file: str, format: str, limit: int):
    """
    View scraped posts from a JSON file.

    Example:
        instagram-scraper view output/saved_posts.json
    """
    import json

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    posts = data.get("posts", [])

    if format == "json":
        console.print_json(data={"posts": posts[:limit]})
        return

    if format == "csv":
        import csv
        import sys
        writer = csv.writer(sys.stdout)
        writer.writerow(["shortcode", "username", "date", "likes", "caption"])
        for post in posts[:limit]:
            writer.writerow([
                post["shortcode"],
                post["owner_username"],
                post["timestamp"][:10],
                post["likes"],
                post["caption"][:200].replace("\n", " "),
            ])
        return

    # Table format
    console.print(f"\n[bold]Saved Posts ({len(posts)} total)[/bold]\n")

    table = Table(show_header=True)
    table.add_column("#", style="dim")
    table.add_column("Username", style="cyan")
    table.add_column("Date")
    table.add_column("Likes", justify="right")
    table.add_column("Caption Preview")

    for i, post in enumerate(posts[:limit], 1):
        caption = post.get("caption", "")[:50]
        caption = caption.replace("\n", " ")
        if len(post.get("caption", "")) > 50:
            caption += "..."

        table.add_row(
            str(i),
            f"@{post['owner_username']}",
            post["timestamp"][:10],
            str(post["likes"]),
            caption or "(no caption)",
        )

    console.print(table)

    if len(posts) > limit:
        console.print(f"\n[dim]Showing {limit} of {len(posts)} posts. Use --limit to show more.[/dim]")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
