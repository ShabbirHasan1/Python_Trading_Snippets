# alerts you when a stock's volume exceeds 10 standard deviations from the mean within the last 3 days 
# https://github.com/SamPom100/UnusualVolumeDetector
# unusualvolume.info


from ftplib import FTP
import os
import errno

import time
import yfinance as yf
import dateutil.relativedelta
from datetime import date
import datetime
import numpy as np
import sys
from stocklist import NasdaqController
from tqdm import tqdm
from joblib import Parallel, delayed, parallel_backend
import multiprocessing


# this is used to get all tickers from the market.


exportList = []


class NasdaqController:
    def getList(self):
        return exportList

    def __init__(self, update=True):

        self.filenames = {
            "otherlisted": "data/otherlisted.txt",
            "nasdaqlisted": "data/nasdaqlisted.txt"
        }

        # Update lists only if update = True

        if update == True:
            self.ftp = FTP("ftp.nasdaqtrader.com")
            self.ftp.login()

            #print("Nasdaq Controller: Welcome message: " + self.ftp.getwelcome())

            self.ftp.cwd("SymbolDirectory")

            for filename, filepath in self.filenames.items():
                if not os.path.exists(os.path.dirname(filepath)):
                    try:
                        os.makedirs(os.path.dirname(filepath))
                    except OSError as exc:  # Guard against race condition
                        if exc.errno != errno.EEXIST:
                            raise

                self.ftp.retrbinary("RETR " + filename +
                                    ".txt", open(filepath, 'wb').write)

        all_listed = open("data/alllisted.txt", 'w')

        for filename, filepath in self.filenames.items():
            with open(filepath, "r") as file_reader:
                for i, line in enumerate(file_reader, 0):
                    if i == 0:
                        continue

                    line = line.strip().split("|")

                    # line[6] and line[4] is for ETFs. Let's skip those to make this faster.
                    if line[0] == "" or line[1] == "" or (filename == 'nasdaqlisted' and line[6] == 'Y') or (filename == 'otherlisted' and line[4] == 'Y'):
                        continue

                    all_listed.write(line[0] + ",")
                    global exportList
                    exportList.append(line[0])
                    all_listed.write(line[0] + "|" + line[1] + "\n")


# Change variables to your liking then run the script
MONTH_CUTTOFF = 5
DAY_CUTTOFF = 3
STD_CUTTOFF = 9


class mainObj:

    def __init__(self):
        pass

    def getData(self, ticker):
        global MONTH_CUTOFF
        currentDate = datetime.date.today() + datetime.timedelta(days=1)
        pastDate = currentDate - \
            dateutil.relativedelta.relativedelta(months=MONTH_CUTTOFF)
        sys.stdout = open(os.devnull, "w")
        data = yf.download(ticker, pastDate, currentDate)
        sys.stdout = sys.__stdout__
        return data[["Volume"]]

    def find_anomalies(self, data):
        global STD_CUTTOFF
        indexs = []
        outliers = []
        data_std = np.std(data['Volume'])
        data_mean = np.mean(data['Volume'])
        anomaly_cut_off = data_std * STD_CUTTOFF
        upper_limit = data_mean + anomaly_cut_off
        data.reset_index(level=0, inplace=True)
        for i in range(len(data)):
            temp = data['Volume'].iloc[i]
            if temp > upper_limit:
                indexs.append(str(data['Date'].iloc[i])[:-9])
                outliers.append(temp)
        d = {'Dates': indexs, 'Volume': outliers}
        return d

    def customPrint(self, d, tick):
        print("\n\n\n*******  " + tick.upper() + "  *******")
        print("Ticker is: "+tick.upper())
        for i in range(len(d['Dates'])):
            str1 = str(d['Dates'][i])
            str2 = str(d['Volume'][i])
            print(str1 + " - " + str2)
        print("*********************\n\n\n")

    def days_between(self, d1, d2):
        d1 = datetime.datetime.strptime(d1, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(d2, "%Y-%m-%d")
        return abs((d2 - d1).days)

    def parallel_wrapper(self, x, currentDate, positive_scans):
        global DAY_CUTTOFF
        d = (self.find_anomalies(self.getData(x)))
        if d['Dates']:
            for i in range(len(d['Dates'])):
                if self.days_between(str(currentDate)[:-9], str(d['Dates'][i])) <= DAY_CUTTOFF:
                    self.customPrint(d, x)
                    stonk = dict()
                    stonk['Ticker'] = x
                    stonk['TargetDate'] = d['Dates'][0]
                    stonk['TargetVolume'] = str(
                        '{:,.2f}'.format(d['Volume'][0]))[:-3]
                    positive_scans.append(stonk)

    def main_func(self):
        StocksController = NasdaqController(True)
        list_of_tickers = StocksController.getList()
        currentDate = datetime.datetime.strptime(
            date.today().strftime("%Y-%m-%d"), "%Y-%m-%d")
        start_time = time.time()

        manager = multiprocessing.Manager()
        positive_scans = manager.list()

        with parallel_backend('loky', n_jobs=multiprocessing.cpu_count()):
            Parallel()(delayed(self.parallel_wrapper)(x, currentDate, positive_scans)
                       for x in tqdm(list_of_tickers))

        print("\n\n\n\n--- this took %s seconds to run ---" %
              (time.time() - start_time))

        return positive_scans


if __name__ == '__main__':
    mainObj().main_func()