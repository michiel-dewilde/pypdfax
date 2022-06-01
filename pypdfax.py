import argparse, glob, img2pdf, io, os, shutil, subprocess, tempfile
from PIL import Image, ImageChops, ImageFilter

def get_trim_bbox(img, tolerance=0.3, blur=0, backout=0):
    if blur != 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    bg = Image.new('L', img.size, 255)
    diff = ImageChops.difference(img, bg)
    tmp = ImageChops.constant(diff, int(tolerance * 255))
    diff = ImageChops.subtract(diff, tmp)
    size = img.size
    bbox = diff.getbbox()
    backout = int(backout)
    bbox = (max(bbox[0]-backout, 0), max(bbox[1]-backout, 0), min(bbox[2]+backout, size[0]), min(bbox[3]+backout, size[1]))
    return bbox

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("output")
parser.add_argument("--input-resolution", type=int, default=600)
parser.add_argument("--cutmm", type=float, default=0.0)
parser.add_argument("--cutl", type=float, default=None)
parser.add_argument("--cutr", type=float, default=None)
parser.add_argument("--cutt", type=float, default=None)
parser.add_argument("--cutb", type=float, default=None)
parser.add_argument("--output-resolution", type=int, default=600)
parser.add_argument("--threshold", type=float, default=0.5)
parser.add_argument("--blur", type=float, default=0)
args = parser.parse_args()

gss = glob.glob(os.path.join(os.environ["PROGRAMFILES"], "gs", "gs*", "bin", "gswin64c.exe"))
assert len(gss) == 1
gs = gss[0]

inch = 25.4
a4w = 210.0
a4h = 297.0
margin = 6.35

max_width_out = a4w - 2*margin
max_height_out = a4h - 2*margin

a4inpt = (img2pdf.mm_to_pt(a4w),img2pdf.mm_to_pt(a4h))
def layout_fun(imgwidthpx, imgheightpx, ndpi):
    imgwidthpdf = img2pdf.px_to_pt(imgwidthpx, ndpi[0])
    imgheightpdf = img2pdf.px_to_pt(imgheightpx, ndpi[1])
    return a4inpt[0], a4inpt[1], imgwidthpdf, imgheightpdf

cutl = int(round((args.cutl if args.cutl is not None else args.cutmm) / inch * args.input_resolution))
cutr = int(round((args.cutr if args.cutr is not None else args.cutmm) / inch * args.input_resolution))
cutt = int(round((args.cutt if args.cutt is not None else args.cutmm) / inch * args.input_resolution))
cutb = int(round((args.cutb if args.cutb is not None else args.cutmm) / inch * args.input_resolution))

def readimg(tmp_dir, pageidx):
    pngfile = os.path.join(tmp_dir, f"{pageidx+1:06d}.png")
    img = Image.open(pngfile)
    img = img.crop((cutl, cutt, img.size[0] - cutr, img.size[1] - cutb))
    return img

with tempfile.TemporaryDirectory() as tmp_dir:
    output_template = os.path.join(tmp_dir, "%06d.png")
    subprocess.check_call([gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pnggray", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
        f"-r{args.input_resolution}", f"-sOutputFile={output_template}", args.input])

    pagecount = len(os.listdir(tmp_dir))

    trim_bboxes = []

    for pageidx in range(pagecount):
        img = readimg(tmp_dir, pageidx)
        trim_blur = 4*args.input_resolution/600
        trim_backout = 20*args.input_resolution/600
        bbox = get_trim_bbox(img, blur=trim_blur, backout=trim_backout)
        trim_bboxes.append(bbox)

    max_width_in = max(bbox[2] - bbox[0] for bbox in trim_bboxes) * inch / args.input_resolution
    max_height_in = max(bbox[3] - bbox[1] for bbox in trim_bboxes) * inch / args.input_resolution

    scale = min(max_width_out/max_width_in, max_height_out/max_height_in)
    supersample = scale * args.output_resolution / args.input_resolution

    images = []

    for pageidx in range(pagecount):
        img = readimg(tmp_dir, pageidx)
        img = img.resize((round(supersample * img.size[0]), round(supersample * img.size[1])), Image.BICUBIC)
        trim_bbox = trim_bboxes[pageidx]
        trim_bbox = (max(round(supersample * trim_bbox[0]), 0), max(round(supersample * trim_bbox[1]), 0), 
            min(round(supersample * trim_bbox[2]), img.size[0]), min(round(supersample * trim_bbox[3]), img.size[1]))
        blur = args.blur * scale
        if blur != 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))
        img = img.crop(trim_bbox)
        img = img.point(lambda x: 255 if x >= 255*args.threshold else 0).convert('1')
        bio = io.BytesIO()
        img.save(bio, format="TIFF", dpi=(args.output_resolution, args.output_resolution), compression="group4")
        images.append(bio.getvalue())

    with open(args.output, "wb") as of:
        of.write(img2pdf.convert(images, layout_fun=layout_fun))
