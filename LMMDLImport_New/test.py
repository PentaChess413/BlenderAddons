from mdl import *
from construct import *

mdldata = MDL.parse_file("../hr_mdl.mdl")
print(mdldata)
textures = mdldata.textures
for texture in textures:
    print(len(texture.texdata))
    print(texture.height)
    print(texture.width)