import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmcplugin
import os
import simplejson
import hashlib
import urllib
from PIL import Image, ImageOps
from ImageOperations import MyGaussianBlur
from xml.dom.minidom import parse

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_LANGUAGE = ADDON.getLocalizedString
ADDON_DATA_PATH = os.path.join(xbmc.translatePath("special://profile/addon_data/%s" % ADDON_ID))
HOME = xbmcgui.Window(10000)


class TextViewer_Dialog(xbmcgui.WindowXMLDialog):
    ACTION_PREVIOUS_MENU = [9, 92, 10]

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self)
        self.text = kwargs.get('text')
        self.header = kwargs.get('header')

    def onInit(self):
        self.getControl(1).setLabel(self.header)
        self.getControl(5).setText(self.text)

    def onAction(self, action):
        if action in self.ACTION_PREVIOUS_MENU:
            self.close()

    def onClick(self, controlID):
        pass

    def onFocus(self, controlID):
        pass


def RemoveQuotes(label):
    if label.startswith("'") and label.endswith("'") and len(label) > 2:
        label = label[1:-1]
        if label.startswith('"') and label.endswith('"') and len(label) > 2:
            label = label[1:-1]
    return label


def AddArtToLibrary(type, media, folder, limit, silent=False):
    json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.Get%ss", "params": {"properties": ["art", "file"], "sort": { "method": "label" } }, "id": 1}' % media.lower())
    json_query = unicode(json_query, 'utf-8', errors='ignore')
    json_response = simplejson.loads(json_query)
    if (json_response['result'] is not None) and ('%ss' % (media.lower()) in json_response['result']):
        # iterate through the results
        if not silent:
            progressDialog = xbmcgui.DialogProgress(ADDON_LANGUAGE(32016))
            progressDialog.create(ADDON_LANGUAGE(32016))
        for count, item in enumerate(json_response['result']['%ss' % media.lower()]):
            if not silent:
                if progressDialog.iscanceled():
                    return
            path = os.path.join(media_path(item['file']).encode("utf-8"), folder)
            file_list = xbmcvfs.listdir(path)[1]
            for i, file in enumerate(file_list):
                if i + 1 > limit:
                    break
                if not silent:
                    progressDialog.update((count * 100) / json_response['result']['limits']['total'], ADDON_LANGUAGE(32011) + ' %s: %s %i' % (item["label"], type, i + 1))
                    if progressDialog.iscanceled():
                        return
                # just in case someone uses backslahes in the path
                # fixes problems mentioned on some german forum
                file_path = os.path.join(path, file).encode('string-escape')
                if xbmcvfs.exists(file_path) and item['art'].get('%s%i' % (type, i), '') == "":
                    xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.Set%sDetails", "params": { "%sid": %i, "art": { "%s%i": "%s" }}, "id": 1 }' %
                                        (media, media.lower(), item.get('%sid' % media.lower()), type, i + 1, file_path))


def media_path(path):
    # Check for stacked movies
    try:
        path = os.path.split(path)[0].rsplit(' , ', 1)[1].replace(",,", ",")
    except:
        path = os.path.split(path)[0]
    # Fixes problems with rared movies and multipath
    if path.startswith("rar://"):
        path = os.path.split(urllib.url2pathname(path.replace("rar://", "")))[0]
    elif path.startswith("multipath://"):
        temp_path = path.replace("multipath://", "").split('%2f/')
        path = urllib.url2pathname(temp_path[0])
    return path


def import_skinsettings():
    importstring = read_from_file()
    if importstring:
        progressDialog = xbmcgui.DialogProgress(ADDON_LANGUAGE(32010))
        progressDialog.create(ADDON_LANGUAGE(32010))
        xbmc.sleep(200)
        for count, skinsetting in enumerate(importstring):
            if progressDialog.iscanceled():
                return
            if skinsetting[1].startswith(xbmc.getSkinDir()):
                progressDialog.update((count * 100) / len(importstring), ADDON_LANGUAGE(32011) + ' %s' % skinsetting[1])
                setting = skinsetting[1].replace(xbmc.getSkinDir() + ".", "")
                if skinsetting[0] == "string":
                    if skinsetting[2] is not "":
                        xbmc.executebuiltin("Skin.SetString(%s,%s)" % (setting, skinsetting[2]))
                    else:
                        xbmc.executebuiltin("Skin.Reset(%s)" % setting)
                elif skinsetting[0] == "bool":
                    if skinsetting[2] == "true":
                        xbmc.executebuiltin("Skin.SetBool(%s)" % setting)
                    else:
                        xbmc.executebuiltin("Skin.Reset(%s)" % setting)
            xbmc.sleep(30)
        xbmcgui.Dialog().ok(ADDON_LANGUAGE(32005), ADDON_LANGUAGE(32009))
    else:
        log("backup not found")


def Filter_Image(filterimage, radius):
    if not xbmcvfs.exists(ADDON_DATA_PATH):
        xbmcvfs.mkdir(ADDON_DATA_PATH)
    md5 = hashlib.md5(filterimage).hexdigest()
    filename = md5 + str(radius) + ".png"
    targetfile = os.path.join(ADDON_DATA_PATH, filename)
    cachedthumb = xbmc.getCacheThumbName(filterimage)
    xbmc_vid_cache_file = os.path.join("special://profile/Thumbnails/Video", cachedthumb[0], cachedthumb)
    xbmc_cache_file = os.path.join("special://profile/Thumbnails/", cachedthumb[0], cachedthumb[:-4] + ".jpg")
    if filterimage == "":
        return "", ""
    if not xbmcvfs.exists(targetfile):
        img = None
        for i in range(1, 4):
            try:
                if xbmcvfs.exists(xbmc_cache_file):
                    log("image already in xbmc cache: " + xbmc_cache_file)
                    img = Image.open(xbmc.translatePath(xbmc_cache_file))
                    break
                elif xbmcvfs.exists(xbmc_vid_cache_file):
                    log("image already in xbmc video cache: " + xbmc_vid_cache_file)
                    img = Image.open(xbmc.translatePath(xbmc_vid_cache_file))
                    break
                else:
                    filterimage = urllib.unquote(filterimage.replace("image://", "")).decode('utf8')
                    if filterimage.endswith("/"):
                        filterimage = filterimage[:-1]
                    log("copy image from source: " + filterimage)
                    xbmcvfs.copy(filterimage, targetfile)
                    img = Image.open(targetfile)
                    break
            except:
                log("Could not get image for %s (try %i)" % (filterimage, i))
                xbmc.sleep(500)
        if not img:
            return "", ""
        img.thumbnail((200, 200), Image.ANTIALIAS)
        img = img.convert('RGB')
        imgfilter = MyGaussianBlur(radius=radius)
        img = img.filter(imgfilter)
        img.save(targetfile)
    else:
        log("blurred img already created: " + targetfile)
        img = Image.open(targetfile)
    imagecolor = Get_Colors(img)
    return targetfile, imagecolor


def Get_Colors(img):
    width, height = img.size
    pixels = img.load()
    data = []
    for x in range(width / 2):
        for y in range(height / 2):
            cpixel = pixels[x * 2, y * 2]
            data.append(cpixel)
    r = 0
    g = 0
    b = 0
    counter = 0
    for x in range(len(data)):
        brightness = data[x][0] + data[x][1] + data[x][2]
        if brightness > 150 and brightness < 720:
            r += data[x][0]
            g += data[x][1]
            b += data[x][2]
            counter += 1
    if counter > 0:
        rAvg = int(r / counter)
        gAvg = int(g / counter)
        bAvg = int(b / counter)
        Avg = (rAvg + gAvg + bAvg) / 3
        minBrightness = 130
        if Avg < minBrightness:
            Diff = minBrightness - Avg
            if rAvg <= (255 - Diff):
                rAvg += Diff
            else:
                rAvg = 255
            if gAvg <= (255 - Diff):
                gAvg += Diff
            else:
                gAvg = 255
            if bAvg <= (255 - Diff):
                bAvg += Diff
            else:
                bAvg = 255
        imagecolor = "FF%s%s%s" % (format(rAvg, '02x'), format(gAvg, '02x'), format(bAvg, '02x'))
    else:
        imagecolor = "FFF0F0F0"
    log("Average Color: " + imagecolor)
    return imagecolor


def image_recolorize(src, black="#000099", white="#99CCFF"):
    # img = image_recolorize(img, black="#000000", white="#FFFFFF")
    """
    Returns a recolorized version of the initial image using a two-tone
    approach. The color in the black argument is used to replace black pixels
    and the color in the white argument is used to replace white pixels.

    The defaults set the image to a blue hued image.
    """
    return ImageOps.colorize(ImageOps.grayscale(src), black, white)


def save_to_file(content, filename, path=""):
    if path == "":
        path = get_browse_dialog()
        if not path:
            return ""
        text_file_path = "%s%s.txt" % (path, filename)
    else:
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdir(path)
        text_file_path = os.path.join(path, filename + ".txt")
    log("save to textfile: " + text_file_path)
    text_file = xbmcvfs.File(text_file_path, "w")
    simplejson.dump(content, text_file)
    text_file.close()
    return True


def read_from_file(path=""):
    if path == "":
        path = get_browse_dialog(dlg_type=1)
    if xbmcvfs.exists(path):
        f = xbmcvfs.File(path)
        fc = simplejson.load(f)
        log("loaded textfile " + path)
        return fc
    else:
        return False


def JumpToLetter(letter):
    if not xbmc.getInfoLabel("ListItem.Sortletter")[0] == letter:
        xbmc.executebuiltin("SetFocus(50)")
        if letter in ["A", "B", "C", "2"]:
            jumpsms_id = "2"
        elif letter in ["D", "E", "F", "3"]:
            jumpsms_id = "3"
        elif letter in ["G", "H", "I", "4"]:
            jumpsms_id = "4"
        elif letter in ["J", "K", "L", "5"]:
            jumpsms_id = "5"
        elif letter in ["M", "N", "O", "6"]:
            jumpsms_id = "6"
        elif letter in ["P", "Q", "R", "S", "7"]:
            jumpsms_id = "7"
        elif letter in ["T", "U", "V", "8"]:
            jumpsms_id = "8"
        elif letter in ["W", "X", "Y", "Z", "9"]:
            jumpsms_id = "9"
        else:
            jumpsms_id = None
        if jumpsms_id:
            for i in range(1, 5):
                # xbmc.executebuiltin("jumpsms" + jumpsms_id)
                xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Input.ExecuteAction", "params": { "action": "jumpsms%s" }, "id": 1 }' % (jumpsms_id))
                # prettyprint(response)
                xbmc.sleep(15)
                if xbmc.getInfoLabel("ListItem.Sortletter")[0] == letter:
                    break
        xbmc.executebuiltin("SetFocus(24000)")


def export_skinsettings(filter_label=False):
    guisettings_path = xbmc.translatePath('special://profile/guisettings.xml').decode("utf-8")
    if xbmcvfs.exists(guisettings_path):
        log("guisettings.xml found")
        doc = parse(guisettings_path)
        skinsettings = doc.documentElement.getElementsByTagName('setting')
        newlist = []
        for count, skinsetting in enumerate(skinsettings):
            if skinsetting.childNodes:
                value = skinsetting.childNodes[0].nodeValue
            else:
                value = ""
            setting_name = skinsetting.attributes['name'].nodeValue
            if setting_name.startswith(xbmc.getSkinDir()):
                if not filter_label or filter_label in setting_name:
                    newlist.append((skinsetting.attributes['type'].nodeValue, setting_name, value))
        if save_to_file(newlist, xbmc.getSkinDir() + ".backup"):
            xbmcgui.Dialog().ok(ADDON_LANGUAGE(32005), ADDON_LANGUAGE(32006))
    else:
        xbmcgui.Dialog().ok(ADDON_LANGUAGE(32007), ADDON_LANGUAGE(32008))
        log("guisettings.xml not found")


def GetPlaylistStats(path):
    startindex = -1
    endindex = -1
    if (".xsp" in path) and ("special://" in path):
        startindex = path.find("special://")
        endindex = path.find(".xsp") + 4
    elif "library://" in path:
        startindex = path.find("library://")
        endindex = path.rfind("/") + 1
    elif "videodb://" in path:
        startindex = path.find("videodb://")
        endindex = path.rfind("/") + 1
    if (startindex > 0) and (endindex > 0):
        playlistpath = path[startindex:endindex]
    #   json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter": {"field": "path", "operator": "contains", "value": "%s"}, "properties": ["playcount", "resume"]}, "id": 1}' % (playlistpath))
        json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetDirectory", "params": {"directory": "%s", "media": "video", "properties": ["playcount", "resume"]}, "id": 1}' % (playlistpath))
        json_query = unicode(json_query, 'utf-8', errors='ignore')
        json_response = simplejson.loads(json_query)
        if "result" in json_response:
            played = 0
            inprogress = 0
            numitems = json_response["result"]["limits"]["total"]
            for item in json_response["result"]["files"]:
                if "playcount" in item:
                    if item["playcount"] > 0:
                        played += 1
                    if item["resume"]["position"] > 0:
                        inprogress += 1
            HOME.setProperty('PlaylistWatched', str(played))
            HOME.setProperty('PlaylistUnWatched', str(numitems - played))
            HOME.setProperty('PlaylistInProgress', str(inprogress))
            HOME.setProperty('PlaylistCount', str(numitems))


def CreateDialogSelect(header):
    selectionlist = []
    indexlist = []
    for i in range(1, 20):
        label = xbmc.getInfoLabel("Window.Property(Dialog.%i.Label)" % (i))
        if label == "":
            break
        elif label != "none" and label != "-":
            selectionlist.append(label)
            indexlist.append(i)
    if selectionlist:
        select_dialog = xbmcgui.Dialog()
        index = select_dialog.select(header, selectionlist)
        if index > -1:
            value = xbmc.getInfoLabel("Window.Property(Dialog.%i.Builtin)" % (indexlist[index]))
            for builtin in value.split("||"):
                xbmc.executebuiltin(builtin)
                xbmc.sleep(30)
    for i in range(1, 20):
        xbmc.executebuiltin("ClearProperty(Dialog.%i.Builtin)" % (i))
        xbmc.executebuiltin("ClearProperty(Dialog.%i.Label)" % (i))


def CreateDialogOK(header, line1):
    dialog = xbmcgui.Dialog()
    dialog.ok(header, line1)


def CreateDialogYesNo(header="", line1="", nolabel="", yeslabel="", noaction="", yesaction=""):
    if yeslabel == "":
        yeslabel = xbmc.getInfoLabel("Window.Property(Dialog.yes.Label)")
        if yeslabel == "":
            yeslabel = "yes"
    if nolabel == "":
        nolabel = xbmc.getInfoLabel("Window.Property(Dialog.no.Label)")
        if nolabel == "":
            nolabel = "no"
    if yesaction == "":
        yesaction = xbmc.getInfoLabel("Window.Property(Dialog.yes.Builtin)")
    if noaction == "":
        noaction = xbmc.getInfoLabel("Window.Property(Dialog.no.Builtin)")
    dialog = xbmcgui.Dialog()
    ret = dialog.yesno(heading=header, line1=line1, nolabel=nolabel, yeslabel=yeslabel)  # autoclose missing
    if ret:
        for builtin in yesaction.split("||"):
            xbmc.executebuiltin(builtin)
            xbmc.sleep(30)
    else:
        for builtin in noaction.split("||"):
            xbmc.executebuiltin(builtin)
            xbmc.sleep(30)
    xbmc.executebuiltin("ClearProperty(Dialog.yes.Label")
    xbmc.executebuiltin("ClearProperty(Dialog.no.Label")
    xbmc.executebuiltin("ClearProperty(Dialog.yes.Builtin")
    xbmc.executebuiltin("ClearProperty(Dialog.no.Builtin")
    return ret


def CreateNotification(header="", message="", icon=xbmcgui.NOTIFICATION_INFO, time=5000, sound=True):
    dialog = xbmcgui.Dialog()
    dialog.notification(heading=header, message=message, icon=icon, time=time, sound=sound)


def GetSortLetters(path, focusedletter):
    listitems = []
    letterlist = []
    HOME.clearProperty("LetterList")
    if ADDON.getSetting("FolderPath") == path:
        letterlist = ADDON.getSetting("LetterList")
        letterlist = letterlist.split()
    else:
        if path:
            json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Files.GetDirectory", "params": {"directory": "%s", "media": "files"}, "id": 1}' % (path))
            json_query = unicode(json_query, 'utf-8', errors='ignore')
            json_response = simplejson.loads(json_query)
            if "result" in json_response and "files" in json_response["result"]:
                for movie in json_response["result"]["files"]:
                    sortletter = movie["label"].replace("The ", "")[0]
                    if sortletter not in letterlist:
                        letterlist.append(sortletter)
            ADDON.setSetting("LetterList", " ".join(letterlist))
            ADDON.setSetting("FolderPath", path)
    HOME.setProperty("LetterList", "".join(letterlist))
    if letterlist and focusedletter:
        startord = ord("A")
        for i in range(0, 26):
            letter = chr(startord + i)
            if letter == focusedletter:
                label = "[B][COLOR FFFF3333]%s[/COLOR][/B]" % letter
            elif letter in letterlist:
                label = letter
            else:
                label = "[COLOR 55FFFFFF]%s[/COLOR]" % letter
            listitem = {"label": label}
            listitems.append(listitem)
    return listitems


def create_channel_list():
    json_response = xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"PVR.GetChannels","params":{"channelgroupid":"alltv", "properties": [ "thumbnail", "locked", "hidden", "channel", "lastplayed" ]}}')
    json_response = unicode(json_response, 'utf-8', errors='ignore')
    json_response = simplejson.loads(json_response)
    if ('result' in json_response) and ("movies" in json_response["result"]):
        return json_response
    else:
        return False


def GetFavouriteswithType(favtype):
    favs = GetFavourites()
    favlist = []
    for fav in favs:
        if fav["Type"] == favtype:
            favlist.append(fav)
    return favlist


def GetFavPath(fav):
    if fav["type"] == "media":
        path = "PlayMedia(%s)" % (fav["path"])
    elif fav["type"] == "script":
        path = "RunScript(%s)" % (fav["path"])
    else:
        path = "ActivateWindow(%s,%s)" % (fav["window"], fav["windowparameter"])
    return path


def GetFavourites():
    items = []
    json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Favourites.GetFavourites", "params": {"type": null, "properties": ["path", "thumbnail", "window", "windowparameter"]}, "id": 1}')
    json_query = unicode(json_query, 'utf-8', errors='ignore')
    json_query = simplejson.loads(json_query)
    if json_query["result"]["limits"]["total"] > 0:
        for fav in json_query["result"]["favourites"]:
            path = GetFavPath(fav)
            newitem = {'Label': fav["title"],
                       'Thumb': fav["thumbnail"],
                       'Type': fav["type"],
                       'Builtin': path,
                       'Path': "plugin://script.extendedinfo/?info=action&&id=" + path}
            items.append(newitem)
    return items


def GetIconPanel(number):
    items = []
    offset = number * 5 - 5
    for i in range(1, 6):
        newitem = {'Label': xbmc.getInfoLabel("Skin.String(IconPanelItem" + str(i + offset) + ".Label)").decode("utf-8"),
                   'Path': "plugin://script.extendedinfo/?info=action&&id=" + xbmc.getInfoLabel("Skin.String(IconPanelItem" + str(i + offset) + ".Path)").decode("utf-8"),
                   'Thumb': xbmc.getInfoLabel("Skin.String(IconPanelItem" + str(i + offset) + ".Icon)").decode("utf-8"),
                   'ID': "IconPanelitem" + str(i + offset).decode("utf-8"),
                   'Type': xbmc.getInfoLabel("Skin.String(IconPanelItem" + str(i + offset) + ".Type)").decode("utf-8")}
        items.append(newitem)
    return items


def log(txt):
    if isinstance(txt, str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (ADDON_ID, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGDEBUG)


def get_browse_dialog(default="", heading="Browse", dlg_type=3, shares="files", mask="", use_thumbs=False, treat_as_folder=False):
    dialog = xbmcgui.Dialog()
    value = dialog.browse(dlg_type, heading, shares, mask, use_thumbs, treat_as_folder, default)
    return value


def Notify(header, line='', line2='', line3=''):
    xbmc.executebuiltin('Notification(%s, %s, %s, %s)' % (header, line, line2, line3))


def prettyprint(string):
    log(simplejson.dumps(string, sort_keys=True, indent=4, separators=(',', ': ')))


def passHomeDataToSkin(data, debug=False):
    if data is not None:
        for (key, value) in data.iteritems():
            HOME.setProperty('%s' % (str(key)), unicode(value))
            if debug:
                log('%s' % (str(key)) + unicode(value))


def passDataToSkin(name, data, prefix="", controlwindow=None, controlnumber=None, handle=None, debug=False):
    if controlnumber is "plugin":
        HOME.clearProperty(name)
        if data is not None:
            HOME.setProperty(name + ".Count", str(len(data)))
            items = CreateListItems(data)
            xbmcplugin.setContent(handle, 'url')
            itemlist = list()
            for item in items:
                itemlist.append((item.getProperty("path"), item, False))
            xbmcplugin.addDirectoryItems(handle, itemlist, False)
    elif controlnumber is not None:
        log("creatin listitems for list with id " + str(controlnumber))
        xbmc.sleep(200)
        itemlist = controlwindow.getControl(controlnumber)
        items = CreateListItems(data)
        itemlist.addItems(items)
    else:
        SetWindowProperties(name, data, prefix, debug)


def SetWindowProperties(name, data, prefix="", debug=False):
    if data is not None:
        # log( "%s%s.Count = %s" % (prefix, name, str(len(data)) ) )
        for (count, result) in enumerate(data):
            if debug:
                log("%s%s.%i = %s" % (prefix, name, count + 1, str(result)))
            for (key, value) in result.iteritems():
                HOME.setProperty('%s%s.%i.%s' % (prefix, name, count + 1, str(key)), unicode(value))
                if debug:
                    log('%s%s.%i.%s --> ' % (prefix, name, count + 1, str(key)) + unicode(value))
        HOME.setProperty('%s%s.Count' % (prefix, name), str(len(data)))
    else:
        HOME.setProperty('%s%s.Count' % (prefix, name), '0')
        log("%s%s.Count = None" % (prefix, name))


def CreateListItems(data=None, preload_images=0):
    Int_InfoLabels = ["year", "episode", "season", "top250", "tracknumber", "playcount", "overlay"]
    Float_InfoLabels = ["rating"]
    String_InfoLabels = ["genre", "director", "mpaa", "plot", "plotoutline", "title", "originaltitle", "sorttitle", "duration", "studio", "tagline", "writer",
                         "tvshowtitle", "premiered", "status", "code", "aired", "credits", "lastplayed", "album", "votes", "trailer", "dateadded"]
    itemlist = []
    if data is not None:
        # threads = []
        # image_requests = []
        for (count, result) in enumerate(data):
            listitem = xbmcgui.ListItem('%s' % (str(count)))
            itempath = ""
            counter = 1
            for (key, value) in result.iteritems():
                if not value:
                    continue
                value = unicode(value)
                # if counter <= preload_images:
                #     if value.startswith("http://") and (value.endswith(".jpg") or value.endswith(".png")):
                #         if value not in image_requests:
                #             thread = Get_File_Thread(value)
                #             threads += [thread]
                #             thread.start()
                #             image_requests.append(value)
                if key.lower() in ["name", "label", "title"]:
                    listitem.setLabel(value)
                elif key.lower() in ["thumb"]:
                    listitem.setThumbnailImage(value)
                elif key.lower() in ["icon"]:
                    listitem.setIconImage(value)
                elif key.lower() in ["path"]:
                    itempath = value
                if key.lower() in ["thumb", "poster", "banner", "fanart", "clearart", "clearlogo", "landscape", "discart", "characterart", "tvshow.fanart", "tvshow.poster", "tvshow.banner", "tvshow.clearart", "tvshow.characterart"]:
                    listitem.setArt({key.lower(): value})
                if key.lower() in Int_InfoLabels:
                    try:
                        listitem.setInfo('video', {key.lower(): int(value)})
                    except:
                        pass
                if key.lower() in String_InfoLabels:
                    listitem.setInfo('video', {key.lower(): value})
                if key.lower() in Float_InfoLabels:
                    try:
                        listitem.setInfo('video', {key.lower(): "%1.1f" % float(value)})
                    except:
                        pass
                listitem.setProperty('%s' % (key), value)
            listitem.setPath(path=itempath)
            listitem.setProperty("index", str(counter))
            itemlist.append(listitem)
            counter += 1
        # for x in threads:
        #     x.join()
    return itemlist



