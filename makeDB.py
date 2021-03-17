import discogs_client
import random as rd
import urllib.request
import shutil
import os
import time


start = time.time()

n = 1 # Number of items in each genres
nameDB = "DB"
genres = ['Jazz', 'Rock', 'Reggae', 'Electronic', 'Hip Hop']


d = discogs_client.Client('makeDB', user_token="lLRjTtAaPNeZDuhfpcMQATfZoUasQwXSVlliVExf")

absPath = os.path.dirname(os.path.abspath(__file__))

if os.path.exists("./" + nameDB): # Deleting the old database
    shutil.rmtree(absPath + '/' + nameDB)
os.mkdir(absPath + '/' + nameDB)
    

for genre in genres:
    os.mkdir(absPath + '/' + nameDB + '/' + genre)

    s = d.search(genre = genre, type = 'release') # search genres
    nbPages = s.pages # Number of pages in the search
    i = 0
    while i != n:
        rdPage = s.page(rd.randint(0, nbPages)) # Random page
        rdRelease = rd.choice(rdPage) # Random release
        url = rdRelease.thumb
        if url != '':
            urllib.request.urlretrieve(url, absPath + '/' + nameDB + '/' + genre + "/" + str(i) + '.jpg')
            i += 1
    
    print(genre + ' is done.')

end = time.time()

print("\nGathered " + str(len(genres)*n) + " items in " + str(round(end - start)) + "s." )