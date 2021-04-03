![](showing.gif)
```py
from os import system
from pathlib import Path

from amsync import Bot, Message
from youtube_dl import YoutubeDL


bot = Bot()

@bot.on()
async def ready():
   print('Ready')


def duration_exceeds(link):
    _3_MIN = 180
    with YoutubeDL() as yt:
        return yt.extract_info(link, download=False)['duration'] > _3_MIN


@bot.add()
async def yt(m: Message):
    link = m.text.split()[0]

    if duration_exceeds(link):
        await bot.send('The video must be less than 3 minutes long')
    else:
        system(f'youtube-dl -x --audio-format mp3 -o "0.mp3" {link}')
        await bot.send(files='0.mp3')
        Path('0.mp3').unlink(missing_ok=True)

bot.run()
```
<br>
<br>
<br>

## Requirements
* youtube-dl
```
pip install youtube-dl
```
<br>

### **Windows**
* [ffmpeg](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z) 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;you need **only** ffmpeg.exe
### **Linux**
```
sudo apt install ffmpeg
```
<br>
<br>
<br>

## Comments
**youtube-dl**: Download songs from youtube
<br>
**ffmpeg**: Required for youtube-dl to convert to mp3
<br>
**Amino**: Accepts audios of up to 3 minutes
<br>
<br>
<br>

## Explanation

```py
def duration_exceeds():
    _3_MIN = 180
    with YoutubeDL() as yt:
        return yt.extract_info(link, download=False)['duration'] > _3_MIN
```

```py
def duration_exceeds(link):
```
Function that checks if the audio is longer than 3 minutes
<br>
<br>
<br>

```py
with YoutubeDL() as yt:
    return yt.extract_info(link, download=False)['duration'] > _3_MIN
```
* We extract information from the video, **without downloading it**
* We get its duration
* We return if the **duration> 3 minutes**
<br>
<br>
<br>

```py
link = m.text.split()[0]

if duration_exceeds(link):
    await bot.send('The video must be less than 3 minutes long')
else:
    system(f'youtube-dl -x --audio-format mp3 -o "0.mp3" {link}')
    await bot.send(files='0.mp3')
    Path('0.mp3').unlink(missing_ok=True)
```
```py
link = m.text.split()[0]
```
We get the first word of the text, which is to be the link
<br>
<br>
<br>

```py
if duration_exceeds():
    await bot.send('The video must be less than 3 minutes long')
else:
    system(f'youtube-dl -x --audio-format mp3 -o "0.mp3" {link}')
    await bot.send(files='0.mp3')
    Path('0.mp3').unlink(missing_ok=True)
```
If the song length is exceeded
* Send a message saying that the song needs to be less than 3 minutes

Senão
* Download the music
* Send the song
* Delete the song (save space)
<br>
<br>
<br>

```py
system(f'youtube-dl -x --audio-format mp3 -o "0.mp3" {link}')
```
**`-x`** Extract audio
\
**`--audio-format mp3`** Convert to mp3
\
**`-o "0.mp3"`** File name will be **0.mp3**