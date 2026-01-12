# Comparisons to other libraries

## OTP-alikes

### `genserver`
Seems to have been mostly abandoned. Weird code, seems undisclosedly vibecoded. Really odd dual structure that has both a regular GenServer and TypedGenServer. Uses threads by default (?????)

### `otpylib`
The API surface seems similar at first glance, but OTPyLib implements a... truly comical amount of things on top that don't really feel needed (for example, why are there functions for internet connectivity? why does it try to recreate *atoms*?)

Meanwhile, `fauxtp` is mostly focused on recreating just the concurrency semantics of Elixir/OTP, while remaining... vaguely kinda not really Pythonic-ish.