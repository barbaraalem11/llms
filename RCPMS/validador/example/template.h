/* ####################################### .h file template ################################################ 
*             
*                     File to be used as a model for using the PT API in other problems
*
*  #########################################################################################################*/
#ifndef __EXAMPLE_H__
#define __EXAMPLE_H__

//#include "../include/Problem.h"



//struct example_encoding: public solution{ 
 
/* ####################################### solution encoding ################################################ 
*            This custom structure extends the "solution"" structure found in the Problem.h file 
*              and should contain variables intended for encoding a solution to the problem

*  #########################################################################################################*/
//};

//class example_class: public Problem<example_encoding>{
//	private:
/* ####################################### Sugestion ################################################ 
*             
*                        Add variables related to the instance to be used in 
*               construction, neighbor and evaluate funtions and othres as you need.  
*
*  ##################################################################################################*/

//	public:
	    // costrution of the class. Sugestion: Read que instance file
//		example_class();
//		~example_class();

/* ####################################### construction ############################################## 
*             
*                Responsible for creating initial solutions. It has no input arguments 
*     and must return the solution created following the encoding established in the previous step. 
*
*  ##################################################################################################*/
//		example_encoding construction();

/* ####################################### neighbor ################################################# 
*             
*     Corresponds to the movement component. It takes a solution as an argument and returns 
*       a neighboring solution generated following the encoding established in the previous step. 
*
*  ##################################################################################################*/
//		example_encoding neighbor(solution sol);

/* ####################################### evaluate ################################################## 
*             
*               Corresponds to the evaluation component. It takes a solution as an argument
*                      and returns the calculated value of the evaluation function. 
*
*  ##################################################################################################*/
//		double evaluate(solution sol);
//};

#endif
