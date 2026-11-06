
# KandaGuide Menu

while True:

    print("\n****** KandaGuide Menu ******")
    print("1. About KandaGuide")
    print("2. Season Check kharif or rabi")
    print("0. Exit")

    choice = input("Enter choice: ")

    if choice == "1":
        print("KandaGuide helps onion and garlic farmers.")

    elif choice == "2":
        season = input("Enter season kharif or rabi ").lower()

        if season == "rabi":
            print("Rabi season selected: ")

        elif season == "kharif":
            print("Kharif season selected: ")

        else:
            print("Invalid  season. ")

    elif choice == "0":
        print("Thank you 😄")
        break

    else:
        print("Invalid choice🫥")
