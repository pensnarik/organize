# organize - a tool to organize images

*organize* is a tool that organize images into folders according to their date and time. The data
and time are determined either from EXIF or from a filename.

## Usage

```bash
oganize.py --src <source fir> --dst <destination dir>
```

The program never overwrites existing file. If a target file exists a suffix containing four-digit
number will be added to the filename.
