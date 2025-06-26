#!/usr/bin/env python3
"""
California Government Ballot Measures Scraper - CLI Interface
"""

import click
from pathlib import Path

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, verbose):
    """California Government Ballot Measures Scraper"""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    if verbose:
        click.echo("🗳️  CA Government Ballot Measures Scraper")

@cli.command()
@click.option('--level', type=click.Choice(['state', 'county', 'city', 'all']), 
              default='state', help='Government level to scrape')
@click.option('--output', '-o', default='data/output.json', help='Output file')
def scrape(level, output):
    """Scrape ballot measures from specified government levels"""
    click.echo(f"🚀 Starting scrape: {level} level")
    click.echo(f"📁 Output: {output}")
    
    # Import and run scraper
    try:
        from ..scrapers.state_scraper import CAStateScraper
        
        scraper = CAStateScraper()
        results = scraper.scrape_all()
        
        # Save results
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
            
        click.echo(f"✅ Scraping completed! Results saved to {output}")
        click.echo(f"📊 Found {len(results.get('measures', []))} items")
        
    except ImportError:
        click.echo("⚠️  Scrapers not implemented yet. Run 'make setup' first.")
    except Exception as e:
        click.echo(f"❌ Error: {e}")

@cli.command()
def status():
    """Show current status and configuration"""
    click.echo("📊 CA Government Scrapers Status")
    click.echo("=" * 40)
    
    # Check if setup is complete
    setup_items = [
        ("Poetry installed", "poetry --version"),
        ("Dependencies installed", "poetry check"),
        ("Data directory", "ls data/ 2>/dev/null"),
        ("Config file", "ls config/scrapers.yaml 2>/dev/null || echo 'Not found'")
    ]
    
    for item, cmd in setup_items:
        import subprocess
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            status = "✅" if result.returncode == 0 else "❌"
            click.echo(f"{status} {item}")
        except:
            click.echo(f"❌ {item}")

if __name__ == '__main__':
    cli()
