import calendar
import re
import numpy as np
from difflib import SequenceMatcher
from sutime import SUTime
from datetime import datetime, timedelta
import traceback
import emoji

sutime = SUTime(mark_time_ranges=True, include_range=True)

def get_date_sut(structured_text):
    return sutime.parse(structured_text)

days_full = [calendar.day_name[i].lower() for i in range(4,7)] # Reduce to saturday and sunday only
days_abbr = [calendar.day_abbr[i].lower() for i in range(4,7)] # Reduce to saturday and sunday only

months_full = [calendar.month_name[i].lower() for i in range(1,13)]
months_abbr = [calendar.month_abbr[i].lower() for i in range(1,13)]

months = list(zip(months_full, months_abbr))
days = list(zip(days_full, days_abbr))
am_pm = ["am", "pm"]
date_subscripts = ["st", "nd", "th"]
compare_lists = [days, months, am_pm, date_subscripts]

words_to_filter = []
with open('frequent_unwanted_words.txt') as f:
    for line in f.readlines():
        word = line.strip()
        if len(word) > 3:
            words_to_filter.append((word, word))

def similar(a, b, use_levis=False):
    return SequenceMatcher(None, a, b).ratio()


def get_begin_time(end, begin_value):
    # This set of time is wrong.
    # We take the end time becuase we are much more confident about it
    candidate_diffs = [1, 0.5, 1.5]
    # get begin candidates. And then compute similarity against the begin value
    begin_cand = []
    for cand in candidate_diffs:
        diff = end - timedelta(hours = cand)
        begin_cand.append((diff.strftime("%I:%M").lower(), diff.strftime("%I:%M")))

    best_begin, _ = get_candidate(begin_value, begin_cand, 0.5)
    begin = datetime.strptime(best_begin, "%H:%M")
    
    return begin

def is_correct_format(date_text, format):
    try:
        datetime.strptime(date_text, format)
    except ValueError:
        # raise ValueError("Incorrect data format, should be ", format)
        # traceback.print_exc()
        return False
    return True

def extract_data(info_per_roi, year = None, sorted_text = None):
    url_data = {
        "day":"",
        "date":"",
        "times":[],
        "times_text":"",
        "start_time":"",
        "end_time":""
    }

    for chunk in info_per_roi[0]:
        if chunk["type"]=="DATE":
            # "Date of Event as Seen on Banner" = chunk["value"]
            # "Day of Week as Shown on Banner" find from the date
            # Note that there could be multiple DATE type chunks in the parser
            # But a false date would be the date which is closest to the current date.
            # If the date that is picked here is farther from today than the previous then select that
            if url_data["date"] != "":
                # Here we make choice between the dates
                today = datetime.today()
                prev_date_diff = abs((today - datetime.strptime(url_data["date"], '%Y-%m-%d')).days)
                candidate_date_diff = abs((today - datetime.strptime(chunk["value"], '%Y-%m-%d')).days)

                if prev_date_diff < candidate_date_diff:
                    # Using the current date if candidate date is farther from todays date than the previous date that was selected
                    url_data["date"] = chunk["value"]
            else:
                url_data["date"] = chunk["value"]

            try:
                # Extracting time from date object
                if "INTERSECT" in url_data["date"]:
                    # Means there is time here
                    splits = url_data["date"].split("INTERSECT")
                    url_data["date"] = splits[0].strip()
                    if len(splits) > 0:
                        for split in splits[1:]:
                            if "T" in split:
                                # extract all cases of \d\d:\d\d
                                time_cands = re.findall("\d\d:\d\d", split)
                                for cand in time_cands:
                                    url_data["times"].append(datetime.strptime(cand, "%H:%M"))
                                    
                if year: 
                    # Check the following two formats and replace year
                    # %Y-%m and %Y-%m-%d
                    formats = ["%Y-%m", "%Y-%m-%d"]
                    for form in formats:
                        # Checking the format
                        if is_correct_format(url_data["date"], form):
                            url_data["date"] = datetime.strptime(url_data["date"], '%Y-%m-%d').replace(year = year).strftime("%Y-%m-%d")
            
            except Exception as e:
                traceback.print_exc()
                print(emoji.emojize(":no_entry_sign: "), e)

            try:
                day = ""
                # Extracting day from the date
                if is_correct_format(url_data["date"], '%Y-%m-%d'):
                    # Extracting from date if the format is perfect
                    day = datetime.strptime(url_data["date"], '%Y-%m-%d').strftime('%A').lower()
                else:
                    # Otherwise relying on extracting day from the text itself
                    sub_chunks = chunk["text"].split(" ")
                    for sub in sub_chunks:
                        _day, conf = get_candidate(sub, days, 0.5)
                        if conf > 0.6:
                            day = _day
                        
                url_data["day"] = day
            except Exception as e:
                traceback.print_exc()
                print(emoji.emojize(":no_entry_sign: "), e)

        elif chunk["type"]=="TIME": 
            # "Start time of Event as seen on Banner" = chunk["value"].split("T") and convert to 12 hour
            # add time to time slots and sort later
            date, value = chunk["value"].split("T")

            if '-' in value:
                # This value contain starting and ending time both.
                # For now just update the value to contain only before the -
                value = value.split("-")[0]

            try:
                # TODO:
                # if there is a am/pm in the chunk["text"] then make sure to override the specify in the date
                d = datetime.strptime(value, "%H:%M")

                url_data["times"].append(d)
            except Exception as e:
                print("Not matching with the provided format")

            # DATE SELECTION
            if is_correct_format(date, '%Y-%m-%d'):
                date = datetime.strptime(date, '%Y-%m-%d').date()
            elif is_correct_format(date, '%Y-WXX-%d'):
                # Create new date with current month
                date = datetime.strptime(date, '%Y-WXX-%d').date()
                
            if type(date) != str:
                if year:
                    date = date.replace(year = year)

                # If we havent seen a date before choose the date parsed with this timestamp
                if url_data["date"] == "":
                    url_data["date"] = str(date)

                    # Day selection ==================
                    day = date.strftime('%A').lower() # Getting day from the date itself
                    sub_chunks = chunk["text"].split(" ") # Getting day from the text with similarity stuff
                    for sub in sub_chunks:
                        _day, conf = get_candidate(sub, days, 0.5)
                        if conf > 0.6:
                            day = _day
                    url_data["day"] = day
                    # ==================
                else:
                    # If we have seen a date. Which may have defaulted to today's date 
                    # and if the current date is not default then overwrite the dates
                    if datetime.today().date() < date:
                        url_data["date"] = str(date)           

                        # ==================
                        day = date.strftime('%A').lower()
                        sub_chunks = chunk["text"].split(" ")
                        for sub in sub_chunks:
                            _day, conf = get_candidate(sub, days, 0.5)
                            if conf > 0.6:
                                day = _day
                        url_data["day"] = day
                        # ==================

            # d.strftime("%I:%M %p")
        elif chunk["type"]=="DURATION":
            # Post process the times as well. 
            # Begin and end most likely contain the same super script.
            url_data["times_text"] = chunk["text"]

            # ==============
            # Date selection
            date = ""
            date_options = [chunk["value"]["begin"].split("T"), chunk["value"]["end"].split("T")]
            for i, d in enumerate(date_options):
                time_ix = 0
                if len(d) >= 2:
                    date_val = d[0]
                    if date != "" and date_val != "":
                        if is_correct_format(date_val[0], '%Y-%m-%d'):
                            date = datetime.strptime(date_val[0], '%Y-%m-%d').date()
                            if year:
                                date = date.replace(year = year)
                    time_ix = 1
                    
                if i == 0:
                    begin = d[time_ix]
                else:
                    end = d[time_ix]
            # ==============

            begin_value = chunk["value"]["begin"].replace("T", "")
            end_value = chunk["value"]["end"].replace("T", "") # We are much more confident about the end time than the begin time
            try:
                # Check if the end time is greater than the begin time
                # If not then confirm also whether the times have a difference greater than 1 hour
                
                begin = datetime.strptime(begin_value, "%H:%M")
                end   = datetime.strptime(end_value, "%H:%M")
                
                # Difference check. The clinics are between an hour and half hour long. Any predicted time which
                diff = begin - end
                diff = abs(diff.total_seconds())
                if diff > 5400: # More than 1.5 hours
                    begin = get_begin_time(end, begin_value)
                
                url_data["times"].append(begin)
                url_data["times"].append(end)
            except:
                traceback.print_exc()
                print("The following times couldnt be converted")
                print(begin_value)
                print(end_value)

    url_data["times"] = sorted(url_data["times"])
    if len(url_data["times"])>=2:
        url_data["start_time"] = url_data["times"][0].strftime("%I:%M %p")
        url_data["end_time"] = url_data["times"][1].strftime("%I:%M %p")
    elif len(url_data["times"])==1:
        url_data["end_time"] = url_data["times"][0].strftime("%I:%M %p")
        
        # Need a candidate begin value here
        # Use regex to extract %d%d:%d%d
        # Need to use_raw_text here
        if sorted_text:
            # Extract all time like objects. Choose the first as begin value
            start_cands = re.findall("\d+:\d\d", sorted_text[0])
            if len(start_cands):
                begin = get_begin_time(end, start_cands[0])
                url_data["start_time"] = begin.strftime("%I:%M %p")
            else:
                # set start time as just the time an hour before the end time 
                url_data["start_time"] = (url_data["times"][0] - timedelta(hours = 1)).strftime("%I:%M %p")
        else:
            url_data["start_time"] = (url_data["times"][0] - timedelta(hours = 1)).strftime("%I:%M %p")
            

    return url_data


def get_candidate(text, compare_list, match_thresh):
    """
    Returns a month, day from the list with a confidence measure
    """
    
    scores = np.array([(similar(text, c), similar(text, c_abbr)) for c, c_abbr in compare_list])
    scores = scores.max(axis=1)
    scores = np.vstack((scores, np.arange(0, scores.shape[0], 1)))
    scores = scores[:, scores[0, :] >  match_thresh]
    
    if 0 in scores.shape:
        return None, 0
    
    best_c = scores[:, scores[0, :].argmax()]
    return compare_list[int(best_c[1])][0], scores[0, :].max()

def post_process_text(text):
    text = re.sub(r'oo', "00",  text)
    text = re.sub(r'oq', "00",  text)
    text = re.sub(r'qo', "00",  text)
    text = re.sub(r'o o', "00",  text)
    text = re.sub(r'(\d)o', "\g<1>0",  text)
    text = re.sub(r'(\d) o', "\g<1>0",  text)
    text = re.sub(r'o(\d)', "0\g<1>",  text)
    text = re.sub(r'o (\d)', "0\g<1>",  text)
    
    # CAUTION. NEW ADDITIONS
    text = re.sub(r'0 0', "00",  text)
    text = re.sub(r': ', ":",  text)
    text = re.sub(r' :', ":",  text)
    text = re.sub(r'-(\d)', "- \g<1>",  text)
    text = re.sub(r'(\d)-', "\g<1> -",  text)
    text = re.sub(r'(\d| |-)00', "\g<1>:00",  text)
    # text = re.sub(r'(\d)q', "\g<1>0",  text)
    text = re.sub(r':(\d)q', ":\g<1>0",  text)

    # Replace ; with :
    # TODO: Detect i's surrounded by numbers or between a (digit and ':'), (digit and st/th/nd), (space and st/nd/th)
    # This is likely a 1. Same for | and l's
    text = re.sub(r'(:| |\d)i(:| |\d|st|nd|th| am| pm|am|pm)', "\g<1>1\g<2>",  text)

    # Connect superscripts to dates
    text = re.sub(r' (st|nd|th)', "\g<1>",  text)

    # Space before am and pm
    text = re.sub(r':(\d\d)(am|pm|[a-z][a-z])', ":\g<1> \g<2>",  text)                     # Create space between the minutes and the period (am|pm)
    text = re.sub(r':(\d\d) mm', ":\g<1> am",  text)                                       # Replace "mm" (usual occurance) with the more likely "am"

    # Colon followed by two digits
    text = re.sub(r': (\d\d)', ":\g<1>",  text)
    text = re.sub(r'(\d) :', "\g<1>:",  text)
    text = re.sub(r'(\d) (00|30)', "\g<1>:\g<2>",  text)

    # Missed 0 conversions
    text = re.sub(r'(\d):(\d)(a-z|A-Z)', "\g<1>:\g<2>0", text)
    text = re.sub(r'(\d:\d\d) (a|p)[a-zA-Z]*', "\g<1> \g<2>m", text)

    # Seperate dates from months
    text = re.sub(r'([a-zA-Z])(%d+) *(th|nd|rd|:)', "\g<1> \g<2>\g<3>", text)

    # The io issue
    text = re.sub(r'io( *th|am|pm|:)', "10\g<1>", text) # If a th is in close proximity the io becomes a 10

    # No space between date and month
    text = re.sub(r'[a-zA-Z](%d+) *th|nd|rd:', " \g<1>", text)

    # No space between period and next time
    text = re.sub(r'(am|pm) *\d+:\d\d', "\g<1> - ", text)

    # 11 misread as ll
    text = re.sub(r'(ll):', "11", text)

    # Replace semi colon with colons and double colons
    text = text.replace(";", ":")
    text = text.replace("::", ":")

    text = text.replace("~", "-")
    return text

def filter_results(result):
    filtered_results = []
    unpushed_results = []

    # Only start appending to the filtered results list once we see a day
    push_flag = False

    for pred in result:
        text, conf = pred
        valid = False
        text = text.lower()

        # Note that a text may contain multiple words. these words should be treated individually
        # Especially when the text is alpha numeric
        # if re.match("\s*[a-z]+\s*[0-9]+\s*", text):
        texts = [text]
        if len(re.findall("[a-zA-Z]+", text)) and len(re.findall("\d+", text)):
            # If the text contains both alphabest and numerics then split them delimeted by space
            # This is done to essentially split months and dates which (according to testing) get concatenated together into the same detector
            texts = text.strip().split(" ")
            
        for _text in texts:
            # Skip word if not in words_to_filter
            cand_, conf = get_candidate(_text, words_to_filter, 0.9)
            if cand_:
                continue

            # If found overlap with any of the following keep: days, months, am_pm, date_subscripts
            for comp in compare_lists:
                cand_, conf = get_candidate(_text, comp, 0.5)
                if cand_:
                    if (cand_ in days_full or cand_ in months_full) and conf > 0.7:
                        push_flag = True
                    valid = True
            
            # If contains any sort of numerics keep
            disjoint_numerics = [int(x) for x in re.findall(r'\d+', _text)]
            if len(disjoint_numerics):
                valid = True
            
            if valid:
                unpushed_results.append(_text)
                if push_flag:
                    #filtered_results.append((box, _text, conf))
                    filtered_results.append(_text)

    print("Unpushed Results: ", "," .join(unpushed_results))
    return filtered_results

def ex(output):
    filtered_result = filter_results(output)
    print(filtered_result)
    result_np = np.array(filtered_result)
    
    sorted_text = " ".join(result_np[:])
    post_processed_text = post_process_text(sorted_text)

    result_su = get_date_sut(post_processed_text)
    info_per_roi=[]
    info_per_roi.append(result_su)

    ret = extract_data(info_per_roi, sorted_text=sorted_text)
    ret["success"] = True 
    ret["sorted_text"] = sorted_text

    return post_processed_text, result_su, ret