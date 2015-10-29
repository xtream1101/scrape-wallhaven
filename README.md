# scrape-wallhaven

Developed using Python 3.4

Scrape the site http://alpha.wallhaven.cc/ and save all wallpapers.

## Dependencies
- [BeautifulSoup4](https://pypi.python.org/pypi/beautifulsoup4)
- [SQLAlchemy](https://pypi.python.org/pypi/SQLAlchemy)
- [custom_utils](https://github.com/xtream1101/custom-utils)

## Usage
- Any args passed in via the command line will override values in the config file if one is passed in
- You must pass a config file with `save_path` set or `-d` 

`$ python3 main.py -c <config_file> -d </dir/to/download/dir>`  
Set this to run as a cron to keep up to date with the content


##Config file
All values in the config file are optional  
If you do not have `save_dir` set here, you must pass in the path using `-d`  
```
[main]
save_dir = ./test
restart = true
```
