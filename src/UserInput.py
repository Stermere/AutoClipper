# gets user input and handles validation

def get_int(prompt, min, max):
    while True:
        try:
            num = int(input(prompt + f' ({min}-{max}): '))
            if num < min or num > max:
                print(f'Please enter a number between {min} and {max}')
                continue
            return num
        except ValueError:
            print('Please enter a valid number')

def get_bool(prompt):
    while True:
        try:
            val = input(prompt)
            if val.lower() == 'y' or val.lower() == 'yes':
                return True
            elif val.lower() == 'n' or val.lower() == 'no':
                return False
            else:
                print('Please enter yes or no')
        except ValueError:
            print('Please enter yes or no')