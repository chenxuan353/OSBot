import  re
string = input()


mini_test = re.compile(
	u'☕️', re.UNICODE
)

string = mini_test.sub("",string)
print("[Text]", string)
print("=======================================================================")

# try:
# 	emoji_regex = re.compile(
#         u'['
#         u'\U0001F300-\U0001F64F'
#         u'\U0001F680-\U0001F6FF'
#         u'\u2600-\u2B55]+', re.UNICODE)
# 	string = emoji_regex.sub("",string)
# 	print("[UCS-4 STD]", string)
# 	print("=======================================================================")
# 	emoji_regex = re.compile(
#         u'(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])', re.UNICODE)

# 	string = emoji_regex.sub("",string)
# 	print("[2018 EXT]", string)
# 	print("=======================================================================")

# 	emoji_regex = re.compile(
# 			u'('
# 			u'\ud83c[\udf00-\udfff]|'
# 			u'\ud83d[\udc00-\ude4f\ude80-\udeff]|'
# 			u'[\u2600-\u2B55])+', re.UNICODE)
# 	string = emoji_regex.sub("",string)
# 	print("[UCS-2 STD]", string)
# 	print("=======================================================================")
# except:
# 	emoji_regex = re.compile(
# 			u'('
# 			u'\ud83c[\udf00-\udfff]|'
# 			u'\ud83d[\udc00-\ude4f\ude80-\udeff]|'
# 			u'[\u2600-\u2B55])+', re.UNICODE)
# 	string = emoji_regex.sub("",string)
# 	print("[UCS-2 STD]", string)

