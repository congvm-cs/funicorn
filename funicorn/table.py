def find_largest_element(rows, cols, length_array, matrix):
    # Loop through each row
    for i in range(rows):
        # Loop through each column
        for j in range(cols):
            length_array.append(len(str(matrix[i][j])))
    # Sort the length matrix so that we can find the element with the longest length
    length_array.sort()
    # Store that length
    largest_element_length = length_array[-1]

    return largest_element_length


def create_matrix(rows, cols, matrix_to_work_on, matrix):
    # Loop through each row
    for i in range(rows):
        # Append a row to matrix_to_work_on for each row in the matrix passed in
        matrix_to_work_on.append([])
        # Loop through each column
        for j in range(cols):
            # Add a each column of the current row (in string form) to matrix_to_work_on
            matrix_to_work_on[i].append(str(matrix[i][j]))


def make_rows(rows, cols, largest_element_length, rowLength, matrix_to_work_on, final_table, color):
    # Loop through each row
    for i in range(rows):
        # Initialize the row that will we work on currently as a blank string
        current_row = ""
        # Loop trhough each column
        for j in range(cols):
            # If we are using colors then do the same thing but as without (below)
            if ((color != None) and (i == 0)):
                # Only add color if it is in the first column or first row
                current_el = " " + "\033[38;2;" + str(color[0]) + ";" + str(
                    color[1]) + ";" + str(color[2]) + "m" + matrix_to_work_on[i][j] + "\033[0m"
            # If we are not using colors (or j != 0 or i != 0) just add a space and the element that should be in that position to a variable which will store the current element to work on
            else:
                current_el = " " + matrix_to_work_on[i][j]

            # If the raw element is less than the largest length of a raw element (raw element is just the unformatted element passed in)
            if (largest_element_length != len(matrix_to_work_on[i][j])):
                # If we are using colors then add the amount of spaces that is equal to the difference of the largest element length and the current element (minus the length that is added for the color)
                # * The plus two here comes from the one space we would normally need and the fact that we need to account for a space that tbe current element already has
                if (color != None):
                    if (i == 0):
                        current_el = current_el + " " * (largest_element_length - (len(current_el) - len("\033[38;2;" + str(
                            color[0]) + ";" + str(color[1]) + ";" + str(color[2]) + "m" + "\033[0m")) + 2) + "|"
                    # If it is not the first column or first row than it doesn't need to subtract the color length
                    else:
                        current_el = current_el + " " * \
                            (largest_element_length - len(current_el) + 2) + "|"
                # If we are not using color just do the same thing as above when we were using colors for when the row or column is not the first each time
                else:
                    current_el = current_el + " " * \
                        (largest_element_length - len(current_el) + 2) + "|"
            # If the raw element length us equal to the largest length of a raw element then we don't need to add extra spaces
            else:
                current_el = current_el + " " + "|"
            # Now add the current element to the row that we are working on
            current_row += current_el
        # When the entire row that we were working on is done add it as a row to the final table that we will print
        final_table.append("|" + current_row)
    # If we are using color then the length of each row (each row will end up being the same length) equals to the length of the last row (again each row will end up being the same length) minus the length the color will inevitably add if we are using colors
    if (color != None):
        rowLength = len(current_row) - len("\033[38;2;" + str(color[0]) + ";" + str(
            color[1]) + ";" + str(color[2]) + "m" + "\033[0m")
    # Otherwise (we are not using colors) the length of each row will be equal to the length of the last row (each row will end up being the same length)
    else:
        rowLength = len(current_row)
    return rowLength


def print_rows_in_table(final_table, print_headers=True):
    # For each row - print it
    if print_headers:
        print(final_table[0])

    for row in final_table[1::]:
        print(row, end='\r', flush=True)


def print_table(matrix, color=None):
    # Rows equal amount of lists inside greater list
    rows = len(matrix)
    # Cols equal amount of elements inside each list
    cols = len(matrix[0])
    # This is the array to sort the length of each element
    length_array = []
    # This is the variable to store the vakye of the largest length of any element
    largest_element_length = None
    #This is the variable that will store the length of each row
    rowLength = None
    # This is the matrix that we will work with throughout this program (main difference between matrix passed in and this matrix is that the matrix that is passed in doesn't always have elements which are all strings)
    matrix_to_work_on = []
    #This the list in which each row will be one of the final table to be printed
    final_table = []

    largest_element_length = find_largest_element(
        rows, cols, length_array, matrix)
    create_matrix(rows, cols, matrix_to_work_on, matrix)
    rowLength = make_rows(rows, cols, largest_element_length,
                          rowLength, matrix_to_work_on, final_table, color)
    return final_table
