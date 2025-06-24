import random
from pwn import *
from solver import Solver

HOST = "localhost"
PORT = 6101
io = remote(HOST, PORT)

print(f"[*] Connecting to {HOST}:{PORT}")

welcome_msg = io.recvline()
print(f"[*] Server: {welcome_msg.decode().strip()}")

io.recvuntil(b"n = ")
n = int(io.recvline().strip())
print(f"[*] n = {n}")

io.recvuntil(b"y = ")
y = int(io.recvline().strip())
print(f"[*] y = {y}")

inv_y = pow(y, -1, n)

io.sendlineafter(b"Your choice [1/2]:", b"1")

solve = Solver()

log.info("Collecting random values for prediction...")

collected_values = []

for i in range(78):
    io.sendlineafter(b"Give me an s: ", b"3")
    
    response = io.recvuntil(b"Your choice [1/2/3]:", drop=False)
    lines = response.split(b'\n')
    
    for j, line in enumerate(lines):
        if b"Here is" in line:
            if j + 1 < len(lines):
                b_str = lines[j + 1].strip()
                if b_str and b_str.isdigit():
                    b = int(b_str)
                    log.info(f"Round {i}: Got b = {b}")
                    collected_values.append(b)
                    
                    temp_b = b
                    while temp_b > 0:
                        solve.submit(temp_b % (1 << 32))
                        temp_b >>= 32
                    break
    
    io.sendline(b"2")

log.info("Starting prediction phase with DP optimization...")
passed = 0

predictions = []
for i in range(256 - 78):
    pred = solve.predict_randint(
        0,
        115792089237316195423570985008687907853269984665640564039457584007913129639934,
    )
    predictions.append(pred)

for i, b in enumerate(predictions):
    z = random.randint(0, n - 1)
    
    if b % 2 == 0:
        s = (pow(z, 2, n) * inv_y) % n
    else:
        s = pow(z, 2, n)
    
    io.sendlineafter(b"Give me an s: ", str(s).encode())
    
    response = io.recvuntil(b"Your choice [1/2/3]:", drop=False)
    lines = response.split(b'\n')
    
    server_b = None
    for j, line in enumerate(lines):
        if b"Here is" in line:
            if j + 1 < len(lines):
                server_b_str = lines[j + 1].strip()
                if server_b_str and server_b_str.isdigit():
                    server_b = int(server_b_str)
                    break
    
    if b != server_b:
        log.error(f"Prediction failed: predicted {b}, got {server_b}")
        solve.clear_cache()
        exit()
    
    io.sendline(b"1")
    io.sendlineafter(b"Give me a z: ", str(z).encode())
    
    response = io.recvline().strip()
    if b"Good" in response:
        passed += 1
        log.info(f"Round {i} passed (total passed: {passed})")
    else:
        log.error(f"Failed at round {i}: {response}")
        exit()

log.info(f"Completed all {256 - 78} prediction rounds successfully!")
log.info("Cache statistics:")
log.info(f"- Harden cache hits: {len(solve.cache_harden)}")
log.info(f"- Predict cache hits: {len(solve.cache_predict)}")
log.info(f"- Decode cache hits: {len(solve.cache_decode)}")

io.interactive()