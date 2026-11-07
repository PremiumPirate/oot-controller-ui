"""Game files this patcher was built and tested against.

The edits use fixed positions inside these files, so the patcher refuses to run on any
other version. To support another version, see CLAUDE.md ("Supporting another version").
"""

TITLE_ID = 0x0400486024DEC000   # The Legend of Zelda: Ocarina of Time (Switch 2)

FONT = "Font2/Scalable/External.Nin_Ounce_NVN2.bfotf"
BNTX = "UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.bntx"
BLARC = "UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.blarc"
RSTB = "System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable"
ZSDIC = "Pack/ZsDic.pack.zs"

# SHA-256 of the original .zs files, per supported game version
VERSIONS = {
    "update v131072": {
        FONT + ".zs": "fb371ef34f505da2c16fcac49a764798143cb5368f4e6482fa4d16afaff3d578",
        BNTX + ".zs": "26c9232bdbf5e2ad3431add5d92c90553f42bbb37aa4d3e901289c8cda5a0186",
        BLARC + ".zs": "0e377658dfc5e68e21aad87c6fa77ea86df8b3261b65c70cb0e985138d67c4ef",
        RSTB + ".zs": "15bd6f03ce65e943fea7e0c2fc7cee2a9548b54f06ba943bc58ebde6b1cac64e",
        ZSDIC: "1f35801d24503905093bb2f6634e5779c1413ca7e6756421160e44d996e60904",
    },
}
