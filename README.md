Amsync
============

Created with the aim that, anyone with basic knowledge of python, create any bot without much difficulty
<br>
<br>

Installation
==========
```
pip install Asymc
```
<br>
<br>

Minimal example
==============

```py
from amsync import Bot, Message


bot = Bot('email', 'password', prefix='/')

@bot.on()
async def ready():
    print('Ready')

@bot.add()
async def hello(m: Message):
    await bot.send(m.nickname)

bot.run()
```
**[Incredible documentation to create beautiful bots](https://github.com/ellandor/Amsync/blob/main/docs/docs.md)**