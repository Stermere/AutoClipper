# a standalong file for graphing data about twitch chat

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import sys

STAT_INTERVAL = 1

# TODO the data is not guaranteed to be in 1 second intervals so graph by the time of each data point 

def main():
    if (sys.argv.__len__() < 2):
        print('Usage: python3 statGraphs.py <csv file>')
        return

    # Read in the data from the csv file
    my_dtype = np.dtype([('float_field', float), ('float_field2', float), ('int', int), ('int2', int), ('datetime', 'datetime64[ns]'), ('list', 'U100')])
    data_in = np.genfromtxt(sys.argv[1], delimiter='\t', dtype=my_dtype, encoding=None)

    index_line = [x for x in range(0, len(data_in))]

    # convert the index_line to the proper time by multiplying by the interval
    index_line = [x * STAT_INTERVAL for x in index_line]

    data_sentiment = [x[0] for x in data_in]
    data_message_length = [x[1] for x in data_in]
    data_message_count = [x[2] for x in data_in]
    data_user_count = [x[3] for x in data_in]
    data_time = [x[4] for x in data_in]
    data_text_data = [x[5] for x in data_in]

    # set style of the plot
    sns.set_style('darkgrid')

    # make a 3 by 1 plot
    fig, axs = plt.subplots(2, 2, figsize=(10, 10))

    axs = axs.flatten()

    axs[0].set_title('Sentiment')
    axs[1].set_title('Message Length')
    axs[2].set_title('Message Count')
    axs[3].set_title('Message Count (Unique)')


    # set the title of the plot
    fig.suptitle('Chat Stats')

    # set the labels of the plot
    axs[0].set(xlabel='Time', ylabel='Sentiment')
    axs[1].set(xlabel='Time', ylabel='Message Length')
    axs[2].set(xlabel='Time', ylabel='Message Count')
    axs[3].set(xlabel='Time', ylabel='Message Count (Unique)')

    # plot the data
    sns.lineplot(x=index_line, y=data_sentiment, color='red', ax=axs[0], label='Sentiment')
    sns.lineplot(x=index_line, y=data_message_length, color='blue', ax=axs[1], label='Message Length')
    sns.lineplot(x=index_line, y=data_message_count, color='green', ax=axs[2], label='Message Count')
    sns.lineplot(x=index_line, y=data_user_count, color='purple', ax=axs[3], label='Message Count (Unique)')

    plt.show()

if __name__ == "__main__":
    main()