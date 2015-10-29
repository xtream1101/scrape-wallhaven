import os
import sys
import signal
from datetime import datetime
from custom_utils.custom_utils import CustomUtils
from custom_utils.exceptions import *
from custom_utils.sql import *

# Set timezone to UTC
os.environ['TZ'] = 'UTC'


class Wallhaven(CustomUtils):

    def __init__(self, base_dir, restart=False, url_header=None):
        super().__init__()
        # Make sure base_dir exists and is created
        self._base_dir = base_dir

        # Do we need to restart
        self._restart = restart

        # Set url_header
        self._url_header = self._set_url_header(url_header)

        # Setup database
        self._db_setup()

        # Start parsing the site
        self.start()

    def start(self):
        latest = self.get_latest()

        if self._restart is True:
            progress = 0
        else:
            progress = self.sql.get_progress()

        if latest == progress:
            # Nothing new to get
            self.cprint("Already have the latest")
            return

        for i in range(progress + 1, latest + 1):
            self.cprint("Getting wallpaper: " + str(i))
            if self._restart is True:
                check_data = self._db_session.query(Data).filter(Data.id == i).first()
                if check_data is not None:
                    continue

            if self.parse(i) is not False:
                self.sql.update_progress(i)

    def get_latest(self):
        """
        Parse `http://alpha.wallhaven.cc/latest` and get the id of the newest wallpaper
        :return: id of the newest item
        """
        self.cprint("##\tGetting newest upload id...\n")

        url = "http://alpha.wallhaven.cc/latest"
        # get the html from the url
        try:
            soup = self.get_site(url, self._url_header)
        except RequestsError as e:
            print("Error getting latest: " + str(e))
            sys.exit(0)

        max_id = soup.find("section", {"class": "thumb-listing-page"}).find("li").a['href'].split('/')[-1]
        self.cprint("##\tNewest upload: " + max_id + "\n")
        return int(max_id)

    def parse(self, id_):
        """
        Using BeautifulSoup, parse the page for the wallpaper and its properties
        :param id_: id of the book on `http://alpha.wallhaven.cc/wallpaper/`
        :return:
        """
        prop = {}
        prop['id'] = str(id_)

        url = "http://alpha.wallhaven.cc/wallpaper/" + prop['id']
        # get the html from the url
        try:
            soup = self.get_site(url, self._url_header)
        except RequestsError as e:
            print("Error getting (" + url + "): " + str(e))
            return False

        # Find all sidebar data
        sidebar = soup.find("aside", {"id": "showcase-sidebar"})

        #####
        # Get colors
        #####
        prop['colors'] = []
        wp_colors = sidebar.find("ul", {"class": "color-palette"})
        for li in wp_colors.find_all("li"):
            prop['colors'].append(li['style'].split(':')[1])

        #####
        # Get tags
        #####
        prop['tags'] = []
        wp_tags = sidebar.find("ul", {"id": "tags"})
        for li in wp_tags.find_all('li'):
            tag = {}
            tag['purity'] = li.get("class", [])[1]
            tag['id'] = li['data-tag-id']
            tag['name'] = li.find("a", {"class": "tagname"}).getText().strip()
            prop['tags'].append(tag)

        #####
        # Get purity
        #####
        prop['purity'] = sidebar.find("fieldset", {"class": "framed"}).find("label").getText()

        #####
        # Get properties
        #####
        wp_prop = sidebar.find("dl")
        for dt in wp_prop.findAll('dt'):
            prop_name = dt.getText().strip()
            dd = dt.findNext("dd")
            if prop_name == 'Favorites':
                prop_value = dd.getText().strip()
            elif prop_name == 'Uploaded by':
                prop_value = dd.find(attrs={"class": "username"}).getText().strip()
            elif prop_name == "Added":
                prop_value = dd.find("time").get("datetime")
            else:
                prop_value = dd.getText().strip()

            prop[prop_name] = prop_value

        #####
        # Get image
        #####
        img_src = "http:" + soup.find("img", {"id": "wallpaper"}).get('src')

        #####
        # Download images
        #####
        file_ext = self.get_file_ext(img_src)
        file_name = "alphaWallhaven-" + prop['id']

        wallpaper_base_dir = os.path.join(self._base_dir, "wallpapers")
        prop['save_path'], prop['hash'] = self.create_hashed_path(wallpaper_base_dir, file_name)
        prop['save_path'] = os.path.join(prop['save_path'], file_name + file_ext)
        prop['rel_path'] = prop['save_path'].replace(self._base_dir, "")

        date_added = prop['Added'][:19]  # we can remove '+00:00'

        prop['Added'] = int((datetime.strptime(date_added, "%Y-%m-%dT%H:%M:%S") -
                             datetime(1970, 1, 1))
                            .total_seconds()
                            )

        if self.download(img_src, prop['save_path'], self._url_header):
            # Save data
            self._save_meta_data(prop)

        # Everything was successful
        return True

    def _set_url_header(self, url_header):
        if url_header is None:
            # Use default from CustomUtils
            return self.get_default_header()
        else:
            return url_header

    def _save_meta_data(self, data):

        resolution = data['Resolution'].split('x')
        check_data = self._db_session.query(Data).filter(Data.id == data['id']).first()
        if check_data is None:
            wallhaven_data = Data(id=data['id'],
                                  added=data['Added'],
                                  category=data['Category'],
                                  favorites=data['Favorites'],
                                  source=data['Source'],
                                  user=data['Uploaded by'],
                                  size=data['Size'],
                                  views=data['Views'],
                                  hash=data['hash'],
                                  purity=data['purity'],
                                  rel_path=data['rel_path'],
                                  color_1=data['colors'][0],
                                  color_2=data['colors'][1],
                                  color_3=data['colors'][2],
                                  color_4=data['colors'][3],
                                  color_5=data['colors'][4],
                                  resolution_width=resolution[0].strip(),
                                  resolution_height=resolution[1].strip(),
                                  )
            self._db_session.add(wallhaven_data)
            try:
                self._db_session.commit()
            except sqlalchemy.exc.IntegrityError:
                # tried to add an item to the database which was already there
                pass

            # Save tags in their own table
            self._save_tag_data(data['tags'], data['id'])

    def _save_tag_data(self, tags, data_id):
        tag_id_list = []
        for tag in tags:
            tag_id_list.append(tag['id'])
            check_tag = self._db_session.query(Tag).filter(Tag.id == tag['id']).first()
            if check_tag is None:  # If tag does not exist, add it
                wallhaven_tag = Tag(id=tag['id'],
                                    name=tag['name'],
                                    purity=tag['purity'],
                                    )
                self._db_session.add(wallhaven_tag)
        try:
            self._db_session.commit()
        except sqlalchemy.exc.IntegrityError:
            # tried to add an item to the database which was already there
            pass

        # Now add tags to data object in DataTag
        # Needs to be done after the tags have been commited to database
        #   because of forginkey constraint
        for tag_id in tag_id_list:
            check_data_tag = self._db_session.query(DataTag).filter(and_(DataTag.tag_id == tag_id,
                                                                         DataTag.data_id == data_id
                                                                         )
                                                                    ).first()
            if check_data_tag is None:  # If tag does not exist, add it
                wallhaven_data_tag = DataTag(tag_id=tag_id,
                                             data_id=data_id
                                             )
                self._db_session.add(wallhaven_data_tag)

        try:
            self._db_session.commit()
        except sqlalchemy.exc.IntegrityError:
            # tried to add an item to the database which was already there
            pass

    def _db_setup(self):
        # Version of this database
        db_version = 1
        db_file = os.path.join(self._base_dir, "wallhaven.sqlite")
        self.sql = Sql(db_file, db_version)
        is_same_version = self.sql.set_up_db()
        if not is_same_version:
            # Update database to work with current version
            pass

        # Get session
        self._db_session = self.sql.get_session()


class Tag(Base):
    __tablename__ = 'tags'
    id     = Column(Integer,    primary_key=True)
    name   = Column(String(50), nullable=False)
    purity = Column(String(20), nullable=False)


class Data(Base):
    __tablename__ = 'data'
    id        = Column(Integer,     primary_key=True)
    added     = Column(Integer,     nullable=False)
    category  = Column(String(100), nullable=False)
    favorites = Column(Integer,     nullable=False)
    source    = Column(String(120), nullable=False)
    user      = Column(String(80),  nullable=False)
    size      = Column(String(20),  nullable=False)
    views     = Column(Integer,     nullable=False)
    hash      = Column(String(32),  nullable=False)
    purity    = Column(String(20),  nullable=False)
    rel_path  = Column(String(255), nullable=False)
    color_1   = Column(String(7),   nullable=False)
    color_2   = Column(String(7),   nullable=False)
    color_3   = Column(String(7),   nullable=False)
    color_4   = Column(String(7),   nullable=False)
    color_5   = Column(String(7),   nullable=False)
    resolution_width  = Column(Integer, nullable=False)
    resolution_height = Column(Integer, nullable=False)


class DataTag(Base):
    __tablename__ = 'data_tags'
    tag_id  = Column(Integer, ForeignKey(Tag.id))
    data_id = Column(Integer, ForeignKey(Data.id))
    __table_args__ = (
            PrimaryKeyConstraint('tag_id', 'data_id'),
            )


def signal_handler(signal, frame):
    print("")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    if len(sys.argv) < 2:
        print("You must pass in the save directory of the scraper")
        sys.exit(0)

    restart = False
    if len(sys.argv) == 3:
        if sys.argv[2] == 'restart':
            restart = True

    save_dir = CustomUtils().create_path(sys.argv[1], is_dir=True)
    # Start the scraper
    scrape = Wallhaven(save_dir, restart)

    print("")
