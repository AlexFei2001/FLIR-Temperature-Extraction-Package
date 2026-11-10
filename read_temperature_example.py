"""Usage: python read_temperature_example.py path/to/temperature.npy [--x 10 --y 20]."""
import argparse
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('matrix'); p.add_argument('--x', type=int, default=0); p.add_argument('--y', type=int, default=0)
args = p.parse_args()
t = np.load(args.matrix, allow_pickle=False)
if t.ndim != 2 or t.dtype.kind != 'f':
    p.error('Expected a two-dimensional floating-point Celsius temperature export')
if not (0 <= args.y < t.shape[0] and 0 <= args.x < t.shape[1]):
    p.error('Requested zero-based coordinate is outside the matrix')
print('shape (height, width):', t.shape)
print('dtype:', t.dtype, '| units: Celsius')
print('minimum / maximum / mean (C):', t.min(), t.max(), t.mean())
print(f'T[y={args.y}, x={args.x}] = {t[args.y, args.x]:.6f} C')
