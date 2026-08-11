// Packs PNG layers into a multi-resolution .ico. Driven by make-icon.ps1.
//
// Entries are stored as PNG rather than DIB. Windows has supported
// PNG-in-ICO since Vista, it is what electron-builder emits itself, and it
// avoids hand-rolling bottom-up BMP rows plus an AND mask.
//
//   node scripts/pack-icon.mjs <png-dir> <out.ico>
import fs from "node:fs";
import path from "node:path";

const [, , SRC, OUT] = process.argv;
if (!SRC || !OUT) {
  console.error("usage: node pack-icon.mjs <png-dir> <out.ico>");
  process.exit(2);
}

// Must match the sizes make-icon.ps1 renders.
const SIZES = [256, 128, 64, 48, 32, 24];

const layers = SIZES.map((size) => {
  const file = path.join(SRC, `icon-${size}.png`);
  const data = fs.readFileSync(file);
  // Trust nothing: a PNG whose IHDR disagrees with its filename produces an
  // icon Windows renders at the wrong scale, with no error anywhere.
  const w = data.readUInt32BE(16);
  const h = data.readUInt32BE(20);
  if (w !== size || h !== size) throw new Error(`${file} is ${w}x${h}, expected ${size}x${size}`);
  return { size, data };
});

const HEADER = 6;
const ENTRY = 16;
let offset = HEADER + ENTRY * layers.length;

const dir = Buffer.alloc(HEADER);
dir.writeUInt16LE(0, 0); // reserved
dir.writeUInt16LE(1, 2); // type: icon
dir.writeUInt16LE(layers.length, 4);

const entries = layers.map((layer) => {
  const e = Buffer.alloc(ENTRY);
  // 0 means 256 in an ICONDIRENTRY - the field is one byte.
  e.writeUInt8(layer.size >= 256 ? 0 : layer.size, 0);
  e.writeUInt8(layer.size >= 256 ? 0 : layer.size, 1);
  e.writeUInt8(0, 2); // palette size
  e.writeUInt8(0, 3); // reserved
  e.writeUInt16LE(1, 4); // colour planes
  e.writeUInt16LE(32, 6); // bits per pixel
  e.writeUInt32LE(layer.data.length, 8);
  e.writeUInt32LE(offset, 12);
  offset += layer.data.length;
  return e;
});

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, Buffer.concat([dir, ...entries, ...layers.map((l) => l.data)]));
console.log(`wrote ${OUT} (${fs.statSync(OUT).size} bytes, ${layers.length} layers)`);
