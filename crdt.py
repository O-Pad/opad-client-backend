####################################
# https://digitalfreepen.com/2017/10/06/simple-real-time-collaborative-text-editor.html
####################################

# class identifier:
#     def __init__(self, d, s):
#         self.digit = d
#         self.site = s

# class char:
#     def __init__(self, l, v):
#         self.lamport = l
#         self.value = v
#         self.position = []

# def comparePosition(p1, p2):
#     for i in range(min(len(p1), len(p2))):
#         comp = compareIdentifier(p1[i], p2[i])
#         if(comp != 0):
#             return comp

#     if len(p1) < len(p2):
#         return -1
#     elif len(p1) > len(p2):
#         return 1
    
#     return 0


# def compareIdentifier(i1, i2):
#     if i1.digit < i2.digit:
#         return -1
#     elif i1.digit > i2.digit:
#         return 1
#     else:
#         if i1.site < i2.site:
#             return -1
#         elif i1.site > i2.site:
#             return 1
    
#     return 0

# def generatePositionBetween(pos1, pos2, site):
#     if len(pos1) > 0:
#         head1 = pos1[0]
#     else:
#         head1 = identifier(0, site)
    
#     if len(pos2) > 0:
#         head2 = pos2[0]
#     else:
#         head2 = identifier()

# embeddings = []

####################################
# https://github.com/0ip/mahitahi
####################################

# Sample code on github:

# from mahitahi import Doc
# from copy import deepcopy

# init_doc = Doc()
# init_doc.insert(0, "A")
# init_doc.insert(1, "B")
# init_doc.insert(2, "C")
# init_doc.insert(3, "\n")

# a_doc = deepcopy(init_doc)
# a_doc.site = 1
# patch_from_a = a_doc.insert(1, "x")

# b_doc = deepcopy(init_doc)
# b_doc.site = 2
# patch_from_b = b_doc.delete(2)

# a_doc.apply_patch(patch_from_b)

# assert a_doc.text == "AxB\n"

# b_doc.apply_patch(patch_from_a)

# assert b_doc.text == "AxB\n"


from mahitahi.mahitahi import Doc

def convertFileToPositionalEmbeddings(filePath, site):
    with open(filePath, 'r') as in_file:
        crdt_doc = Doc()
        crdt_doc.site = site

        pos = 0
        while True:
            c = in_file.read(1)
            if not c:
                break
            print(pos)
            crdt_doc.insert(pos, c)
            pos += 1
        
        return crdt_doc

doc = convertFileToPositionalEmbeddings("./workdir/newfile", 0)

doc.debug()
