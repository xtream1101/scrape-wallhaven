# scrape-wallhaven

Developed using Python 3.4

Scrape the site http://alpha.wallhaven.cc/ and save all wallpapers.

## Dependencies
- [BeautifulSoup4](https://pypi.python.org/pypi/beautifulsoup4)
- [SQLAlchemy](https://pypi.python.org/pypi/SQLAlchemy)
- [custom_utils](https://github.com/xtream1101/custom-utils)

## Usage
\<restart> is optional and will start checking at 0 again  
`$ python3 main.py "/dir/to/download/dir" <restart>`  
Set this to run as a cron to keep up to date with the content
